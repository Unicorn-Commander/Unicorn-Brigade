"""
Human-in-the-Loop (HITL) Tool

Provides agents with the ability to ask for human input or approval.

This is a critical tool for safety, ethics, and complex decision-making.
When an agent is unsure how to proceed, or requires permission for a
sensitive action, it should use this tool to pause its execution and
request guidance from the user.

Potential Functions:
- ask_question(question, options)
- request_approval(action_description)
"""

class HumanInTheLoop:
    def ask_question(self, question: str, options: list = None) -> str:
        """
        Poses a question to the user and waits for their input.
        The implementation will depend on the frontend interface (e.g., a web UI).
        """
        # This would send a message to the main interface to display a prompt.
        # The function would block until the user responds.
        print(f"AGENT REQUEST: {question}")
        if options:
            print(f"OPTIONS: {options}")
        # In a real system, this would wait for a response from the UI.
        return input("> ")

    def request_approval(self, action_description: str) -> bool:
        """
        Asks the user for a yes/no confirmation for a specific action.
        """
        response = self.ask_question(
            f"Do you approve the following action? {action_description}",
            options=["yes", "no"]
        )
        return response.lower() == 'yes'
