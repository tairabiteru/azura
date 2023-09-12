"""Installation script

This file provides a method for Azura to install or reinstall herself.
"""

from prompt_toolkit import prompt, print_formatted_text, HTML
import os
import sys
import shutil


def install():
    reinstall = False

    print_formatted_text(HTML("<skyblue><b><u>Farore</u></b></skyblue>\n"))

    if os.path.exists(os.path.join(os.getcwd(), "conf.toml")):
        from azura.core.conf import Config
        conf = Config.load()
        root = conf.root
    else:
        root = os.getcwd()

    if os.path.exists(os.path.join(root, ".venv")):
        print_formatted_text(HTML("<ansired>!!! Warning !!!</ansired>\nAn existing virtualenv already exists at the root path.\nDo you want to reinstall it?\n"))

        answer = None
        while answer is None:
            answer = prompt("(yes/no): ").lower()
            if answer not in ["yes", "no"]:
                answer = None
        if answer == "yes":
            shutil.rmtree(os.path.join(root, ".venv"))
            reinstall = True
        else:
            print("Aborted.")
            sys.exit(0)
    
    if reinstall is False:
        print_formatted_text(HTML("Install?"))
        answer = None
        while answer is None:
            answer = prompt("(yes/no): ").lower()
            if answer not in ["yes", "no"]:
                answer = None
        if answer != "yes":
            print("Aborted.")
            sys.exit(0)
    
    print_formatted_text(HTML("<ansired>Beginning installation, please be patient.</ansired>"))
    os.makedirs(".venv")
    print_formatted_text(HTML("<violet>Installing dependencies...</violet>"))
    os.system("pipenv install")
    print_formatted_text(HTML("<violet>Done!</violet>\n\n"))

    if not os.path.exists(os.path.join(root, "conf.toml")):
        print_formatted_text(HTML("<ansired>No conf.toml was found. It must be configured for the bot to run correctly.</ansired>"))
        sys.exit(0)
    
    print_formatted_text(HTML("Would you like to run the bot?"))
    answer = None
    while answer is None:
        answer = prompt("(yes/no): ").lower()
        if answer not in ["yes", "no"]:
            answer = None
    if answer != "yes":
        print("Aborted.")
        sys.exit(0)
    
    os.system(f"pipenv run python {root}")
    
