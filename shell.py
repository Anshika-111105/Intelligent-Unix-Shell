from suggestion_client import get_suggestions

def main():
    while True:
        command = input("myOS> ")
        if command.strip() == "exit":
            break

        suggestions = get_suggestions(command)
        if suggestions:
            print("\nSuggestions:")
            for s in suggestions:
                print(f" - {s['suggestion']} ({s['reason']})")
            print()

        print(f"Executing: {command}\n")

if __name__ == "__main__":
    main()
