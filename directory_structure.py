import os

def print_directory_structure(path, indent=""):
    items = sorted(os.listdir(path))
    for item in items:
        if item.startswith('.'):
            continue  # Skip hidden files
        item_path = os.path.join(path, item)
        print(f"{indent}{item}")
        if os.path.isdir(item_path):
            print_directory_structure(item_path, indent + "  ")

print_directory_structure(".")