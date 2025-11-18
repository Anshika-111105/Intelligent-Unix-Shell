/* intelligent_shell.c
 * Cross-platform C shell core:
 *  - Read / parse / execute loop
 *  - Built-ins: cd, exit, history
 *  - Background job support (&)
 *  - Command logging to SQLite
 *  - IPC to a Python suggestion server via Unix domain socket (Unix) or TCP (fallback)
 * Compile (Linux/macOS): gcc -std=gnu11 -Wall -Wextra core.c -o intelligent_shell -lsqlite3
 * Compile (Windows, MinGW): gcc -std=gnu11 -Wall -Wextra core.c -o intelligent_shell.exe -lsqlite3 -lws2_32
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <errno.h>
#include <signal.h>
#include <fcntl.h>
#include <sqlite3.h>

#if defined(__unix__) || defined(__APPLE__)
#include <unistd.h>
#include <sys/socket.h>
#include <sys/un.h>
#define HAVE_UNIX_SOCKETS 1
#else
#define HAVE_UNIX_SOCKETS 0
#endif

#if !HAVE_UNIX_SOCKETS
/* On Windows include Winsock headers for TCP sockets */
#if defined(_WIN32) || defined(_WIN64)
#include <winsock2.h>
#include <ws2tcpip.h>
#pragma comment(lib, "ws2_32.lib")
#else
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>
#endif
#endif

#define DB_PATH "commands.db"
#define SUGGEST_SOCKET_PATH "/tmp/shell_suggest.sock"
#define MAXLINE 4096
#define MAXARGS 256
/* TCP fallback for suggestion server (matches suggestion server default) */
#define SUGGEST_HOST "127.0.0.1"
#define SUGGEST_PORT 9999
/* Default suggestion model requested from server */
#define DEFAULT_SUGGEST_MODEL "Claude Haiku 4.5"

static sqlite3 *g_db = NULL;

/* Initialize SQLite database and history table */
int init_db(const char *path) {
    int rc = sqlite3_open(path, &g_db);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Cannot open database: %s\n", sqlite3_errmsg(g_db));
        return rc;
    }
    const char *sql = "CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, cmd TEXT NOT NULL, ts DATETIME DEFAULT CURRENT_TIMESTAMP);";
    char *errmsg = NULL;
    rc = sqlite3_exec(g_db, sql, 0, 0, &errmsg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "SQL error: %s\n", errmsg);
        sqlite3_free(errmsg);
        return rc;
    }
    return SQLITE_OK;
}

/* Insert command into history */
void log_command(const char *cmd) {
    if (!g_db || !cmd || strlen(cmd) == 0) return;
    const char *sql = "INSERT INTO history (cmd) VALUES (?);";
    sqlite3_stmt *stmt = NULL;
    if (sqlite3_prepare_v2(g_db, sql, -1, &stmt, NULL) != SQLITE_OK) return;
    sqlite3_bind_text(stmt, 1, cmd, -1, SQLITE_TRANSIENT);
    sqlite3_step(stmt);
    sqlite3_finalize(stmt);
}

/* Print history (most recent N) */
void print_history(int limit) {
    if (!g_db) return;
    const char *sql = "SELECT id, ts, cmd FROM history ORDER BY id DESC LIMIT ?;";
    sqlite3_stmt *stmt = NULL;
    if (sqlite3_prepare_v2(g_db, sql, -1, &stmt, NULL) != SQLITE_OK) return;
    sqlite3_bind_int(stmt, 1, limit);
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        int id = sqlite3_column_int(stmt, 0);
        const unsigned char *ts = sqlite3_column_text(stmt, 1);
        const unsigned char *cmd = sqlite3_column_text(stmt, 2);
        printf("%4d  %s  %s\n", id, ts ? (const char*)ts : "", cmd ? (const char*)cmd : "");
    }
    sqlite3_finalize(stmt);
}

/* Trim whitespace in-place */
char *trim(char *s) {
    if (!s) return s;
    while (*s && (*s == ' ' || *s == '\t' || *s == '\n' || *s == '\r')) s++;
    if (*s == '\0') return s;
    char *end = s + strlen(s) - 1;
    while (end > s && (*end == ' ' || *end == '\t' || *end == '\n' || *end == '\r')) *end-- = '\0';
    return s;
}

/* Simple JSON escaping for double quotes and backslashes (in-place into dst; ensure dst has space) */
static void json_escape(const char *src, char *dst, size_t dstlen) {
    size_t di = 0;
    for (size_t si = 0; src[si] != '\0' && di + 1 < dstlen; ++si) {
        unsigned char c = src[si];
        if (c == '"' || c == '\\') {
            if (di + 2 < dstlen) {
                dst[di++] = '\\';
                dst[di++] = c;
            } else break;
        } else if (c == '\n') {
            if (di + 2 < dstlen) { dst[di++] = '\\'; dst[di++] = 'n'; }
            else break;
        } else {
            dst[di++] = c;
        }
    }
    dst[di] = '\0';
}

/* Parse a command line into argv array. Returns argc. Recognizes '&' to indicate background.
   NOTE: This simple parser doesn't handle quotes or escapes (can be extended). */
int parse_line(char *line, char **argv, int *background) {
    int argc = 0;
    *background = 0;
    char *tok = strtok(line, " \t\n");
    while (tok && argc < MAXARGS - 1) {
        if (strcmp(tok, "&") == 0) {
            *background = 1;
        } else {
            argv[argc++] = tok;
        }
        tok = strtok(NULL, " \t\n");
    }
    argv[argc] = NULL;
    return argc;
}

/* Try a TCP connection to suggestion server on localhost:8888
 * This function returns a malloc'd string on success or NULL on failure.
 * Behavior: try Unix domain socket if available; otherwise try TCP.
 */
char *get_suggestion_tcp(const char *line_prefix, const char *model, int timeout_ms) {
    if (!line_prefix || strlen(line_prefix) == 0) return NULL;
    int sock = -1;
    struct sockaddr_in serv;
    sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) return NULL;
    memset(&serv, 0, sizeof(serv));
    serv.sin_family = AF_INET;
    serv.sin_port = htons(SUGGEST_PORT);
    if (inet_pton(AF_INET, SUGGEST_HOST, &serv.sin_addr) <= 0) {
        close(sock);
        return NULL;
    }
    if (connect(sock, (struct sockaddr*)&serv, sizeof(serv)) < 0) {
        close(sock);
        return NULL;
    }

    char payload[MAXLINE];
    char esc_cmd[MAXLINE];
    json_escape(line_prefix, esc_cmd, sizeof(esc_cmd));
    snprintf(payload, sizeof(payload), "{\"cmd\":\"%s\",\"model\":\"%s\"}\n", esc_cmd, model ? model : DEFAULT_SUGGEST_MODEL);

    ssize_t w = send(sock, payload, (int)strlen(payload), 0);
    if (w <= 0) { close(sock); return NULL; }

    // wait for response with timeout
    fd_set rfds;
    FD_ZERO(&rfds);
    FD_SET(sock, &rfds);
    struct timeval tv;
    tv.tv_sec = timeout_ms / 1000;
    tv.tv_usec = (timeout_ms % 1000) * 1000;
    int sel = select(sock+1, &rfds, NULL, NULL, &tv);
    if (sel <= 0) { close(sock); return NULL; }

    char buf[MAXLINE];
    ssize_t r = recv(sock, buf, sizeof(buf)-1, 0);
    if (r <= 0) { close(sock); return NULL; }
    buf[r] = '\0';
    // Strip trailing newline
    char *nl = strchr(buf, '\n'); if (nl) *nl = '\0';
    char *ret = strdup(buf);
    close(sock);
    return ret;
}

char *get_suggestion(const char *line_prefix, const char *model, int timeout_ms) {
    if (!line_prefix || strlen(line_prefix) == 0) return NULL;
#if HAVE_UNIX_SOCKETS
    /* Prefer Unix domain socket when available (existing behavior) */
    int sock = -1;
    struct sockaddr_un addr;
    sock = socket(AF_UNIX, SOCK_STREAM, 0);
    if (sock >= 0) {
        memset(&addr, 0, sizeof(addr));
        addr.sun_family = AF_UNIX;
        strncpy(addr.sun_path, SUGGEST_SOCKET_PATH, sizeof(addr.sun_path)-1);
        if (connect(sock, (struct sockaddr*)&addr, sizeof(addr)) == 0) {
            char buf[MAXLINE];
            char payload[MAXLINE];
            char esc_cmd[MAXLINE];
            json_escape(line_prefix, esc_cmd, sizeof(esc_cmd));
            snprintf(payload, sizeof(payload), "{\"cmd\":\"%s\",\"model\":\"%s\"}\n", esc_cmd, model ? model : DEFAULT_SUGGEST_MODEL);
            ssize_t w = write(sock, payload, strlen(payload));
            if (w > 0) {
                fd_set rfds;
                FD_ZERO(&rfds);
                FD_SET(sock, &rfds);
                struct timeval tv;
                tv.tv_sec = timeout_ms / 1000;
                tv.tv_usec = (timeout_ms % 1000) * 1000;
                int sel = select(sock+1, &rfds, NULL, NULL, &tv);
                if (sel > 0) {
                    ssize_t r = read(sock, buf, sizeof(buf)-1);
                    if (r > 0) {
                        buf[r] = '\0';
                        char *nl = strchr(buf, '\n'); if (nl) *nl = '\0';
                        char *ret = strdup(buf);
                        close(sock);
                        return ret;
                    }
                }
            }
        }
        close(sock);
    }
#endif
    /* Fallback to TCP (works on Windows and when suggestion server uses TCP) */
    return get_suggestion_tcp(line_prefix, model, timeout_ms);
}

/* Execute external command (simple) */
void exec_command(char **argv, int background) {
    pid_t pid = fork();
    if (pid < 0) {
        perror("fork");
        return;
    }
    if (pid == 0) {
        // child
        // restore default signals
        signal(SIGINT, SIG_DFL);
        signal(SIGQUIT, SIG_DFL);
        if (execvp(argv[0], argv) < 0) {
            fprintf(stderr, "shell: exec failed for %s: %s\n", argv[0], strerror(errno));
            exit(127);
        }
    } else {
        // parent
        if (!background) {
            int status;
            if (waitpid(pid, &status, 0) < 0) perror("waitpid");
        } else {
            printf("[bg] pid %d\n", pid);
        }
    }
}

/* Signal handler for SIGINT in shell (ignore in main shell loop) */
void sigint_handler(int signo) {
    // Just print a newline and reprint prompt in main loop
    write(STDOUT_FILENO, "\n", 1);
}

int main(int argc, char **argv) {
#if defined(_WIN32) || defined(_WIN64)
    /* If building/running on Windows with native Winsock, you must call WSAStartup.
       If you use MinGW and link -lws2_32, add this initialization here:
    WSADATA wsaData;
    if (WSAStartup(MAKEWORD(2,2), &wsaData) != 0) {
        fprintf(stderr, "WSAStartup failed\\n");
        return 1;
    }
    and call WSACleanup() before exit.
    */
#endif

    // Initialize DB
    if (init_db(DB_PATH) != SQLITE_OK) {
        fprintf(stderr, "Warning: SQLite DB unavailable. History will be disabled.\n");
        // continue without DB
        g_db = NULL;
    }

    // Setup signal handling: shell should catch SIGINT and not exit
    struct sigaction sa;
    sa.sa_handler = sigint_handler;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = SA_RESTART;
    sigaction(SIGINT, &sa, NULL);

    char linebuf[MAXLINE];
    char *args[MAXARGS];

    while (1) {
        // Read line
        printf("ish> ");
        fflush(stdout);
        if (!fgets(linebuf, sizeof(linebuf), stdin)) {
            if (feof(stdin)) { printf("\n"); break; }
            continue;
        }
        char *line = trim(linebuf);
        if (strlen(line) == 0) continue;

        // Non-blocking suggestion: we attempt to fetch a suggestion and print it as a hint
        char *suggest_json = get_suggestion(line, DEFAULT_SUGGEST_MODEL, 250); // 250 ms timeout
        if (suggest_json) {
            // Print raw response JSON as hint
            printf("\t[suggestion-json] %s\n", suggest_json);
            free(suggest_json);
        }

        // Builtins: check cd, exit, history
        // Copy line because parse_line uses strtok
        char work[MAXLINE]; strncpy(work, line, sizeof(work)); work[sizeof(work)-1] = '\0';
        int background = 0;
        int argc2 = parse_line(work, args, &background);
        if (argc2 == 0) continue;

        if (strcmp(args[0], "exit") == 0) {
            break;
        } else if (strcmp(args[0], "cd") == 0) {
            const char *dir = args[1] ? args[1] : getenv("HOME");
            if (chdir(dir) != 0) perror("cd");
            // log
            log_command(line);
            continue;
        } else if (strcmp(args[0], "history") == 0) {
            int n = 50; // default
            if (args[1]) n = atoi(args[1]);
            print_history(n);
            continue;
        }

        // Not a builtin: execute
        // Log command before execution so even background jobs are recorded; could also log after
        log_command(line);
        exec_command(args, background);
    }

    if (g_db) sqlite3_close(g_db);

#if defined(_WIN32) || defined(_WIN64)
    /* If you added WSAStartup above, call WSACleanup here. */
#endif

    return 0;
}