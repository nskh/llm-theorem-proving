import subprocess
import os
import argparse
import ollama
from typing import List, Dict
import re

MAX_NUM_ATTEMPTS = 2


class CoqInterface:
    def __init__(self, task_prompt, metaprompt, filename, model="codellama:7b"):
        self.task_prompt = task_prompt
        self.metaprompt = metaprompt
        self.model = model
        self.filename = filename
        self.error_log = "coq_error.log"

    def construct_ollama_prompt(self, first=False, errors=None) -> str:
        if first:
            if errors:
                # TODO(nishant): add error metaprompts
                return f"{self.metaprompt}\n{self.task_prompt}\n{self.construct_error_message(errors)}\n"
            return f"{self.metaprompt}\n{self.task_prompt}\n"
        else:
            if errors:
                return f"Reminder that our task is to: {self.task_prompt}\n{self.construct_error_message(errors)}\n"
            return f"{self.task_prompt}\n"

    def construct_error_message(self, errors) -> str:
        # TODO(nishant): add line numbers to error messages
        if type(errors) is str:
            errordict = self.parse_coq_error(errors)
            print("errordict:", errordict)
            return f"We had an error on line {errordict['line']} at characters {errordict['characters']}. The error type was \"{errordict['message']}\""
        print("errors were not string, returning empty")
        return ""
        # elif type(errors) is list and len(errors) > 1:
        #     print("errors were lists")
        #     return "\n".join(
        #         [f"We had the following errors:\nError: {error}" for error in errors]
        #     )

    def parse_coq_error(self, error_message: str) -> Dict[str, str]:
        """
        Parses a Coq error message into a dictionary with fields 'line', 'characters', 'type', and 'message'.

        Args:
            error_message (str): The Coq error message.

        Returns:
            Dict[str, str]: A dictionary containing the parsed error information.
        """
        error_pattern = re.compile(
            # r"File \"[^\"]*\", line (?P<line>\d+), characters (?P<characters>\d+-\d+):\nError: (?P<type>[^\:]+): (?P<message>.*)"
            r"File \"[^\"]*\", line (?P<line>\d+), characters (?P<characters>\d+-\d+):\nError: (?P<message>.*)"
        )

        match = error_pattern.search(error_message)
        if match:
            return match.groupdict()
        return {}

    def generate_coq_code(self, first=False, errors=None) -> str:
        prompt = self.construct_ollama_prompt(first=first, errors=errors)
        print("Prompt:\n==============\n", prompt)
        response = ollama.chat(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )
        return response["message"]["content"]

    def write_to_file(self, code):
        with open(self.filename, "w") as file:
            file.write(code)

    def run_coqc(self):
        compile_command = ["coqc", self.filename]
        try:
            subprocess.run(
                compile_command,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            return True, "Coq code compiled successfully."
        except subprocess.CalledProcessError as e:
            with open(self.error_log, "w") as log_file:
                log_file.write(e.stderr.decode())
            return False, e.stderr.decode()

    def parse_errors(self):
        if not os.path.exists(self.error_log):
            return "No errors found."

        with open(self.error_log, "r") as log_file:
            errors = log_file.read()

        # Add error parsing logic here, if necessary
        # For now, we'll just return the raw error log
        return errors

    def compile_and_check(self, first: bool = False, errors=None):
        coq_code = self.generate_coq_code(first=first, errors=errors)
        clean_coq_code = self.extract_code_segment(coq_code)
        if clean_coq_code == "":
            print("No code segment found in response. Please try again.")
            return (False, "No code segment found in response.")
        self.write_to_file(clean_coq_code)
        success, message = self.run_coqc()
        if not success:
            errors = self.parse_errors()
            print("=============\nCompilation errors:\n", errors)
            return (False, errors)
        else:
            print(message)
            return (True, None)

    def extract_code_segment(self, text: str) -> str:
        """
        Extracts the code segment from text that is delineated by triple backticks ```.

        Args:
            text (str): The input text containing the code segment.

        Returns:
            str: The extracted code segment, or an empty string if no code segment is found.
        """
        code_pattern = re.compile(r"```(.*?)```", re.DOTALL)
        match = code_pattern.search(text)
        if match:
            matchtext = match.group(1).strip()
            # print("Matched text:\n", matchtext)
            cleaned_text = re.sub(r"```[a-zA-Z]*\n", "", matchtext)
            cleaned_text = re.sub(r"```\s*$", "", cleaned_text, flags=re.MULTILINE)
            # print("Cleaned text:\n", cleaned_text.strip())
            return cleaned_text.strip()
        return ""


def main():
    parser = argparse.ArgumentParser(
        description="Generate and compile Coq code using Ollama API."
    )
    parser.add_argument("prompt", type=str, help="The prompt to generate Coq code.")
    parser.add_argument(
        "--model",
        type=str,
        default="codellama:7b",
        help="The model to use for generating Coq code (e.g., llama3).",
    )
    parser.add_argument(
        "--filename",
        type=str,
        default="temp.v",
        help="The filename to write the Coq code to.",
    )

    args = parser.parse_args()

    metaprompt = """
We're going to play a game. I'll give you a prompt, and you have to write a Coq proof that satisfies the prompt. In your answers, write only one Coq code snippet delineated by triple backticks ```. I'll check your proof and let you know if it's correct. If you need help, just ask!
"""

    coq_handler = CoqInterface(
        model=args.model,
        task_prompt=args.prompt,
        metaprompt=metaprompt,
        filename=args.filename,
    )
    status = False
    errors = None
    for i in range(MAX_NUM_ATTEMPTS):
        status, errors = coq_handler.compile_and_check(first=i == 0, errors=errors)
        if status:
            break
        else:
            print("Errors found. Trying again.\n=============")


if __name__ == "__main__":
    main()
