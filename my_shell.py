from suggestion_client import get_suggestions

def my_shell():
    while True:
        command = input("myOS> ")

        if command.strip().lower() == "exit":
            print("Exiting myOS shell.")
            break

        # get suggestions
        suggestions = get_suggestions(command)
        if suggestions:
            print("\n--- Suggestions ---")
            for s in suggestions:
                print(f"• {s['suggestion']}  ({s['reason']})")
            print("-------------------\n")

        print(f"Executing: {command}\n")

if __name__ == "__main__":
    my_shell()
