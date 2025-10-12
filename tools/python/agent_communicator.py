"""
Agent Communicator Tool

Provides agents with the ability to communicate with other agents.

This tool abstracts the underlying communication protocol (e.g., gRPC).
An agent uses this tool to send messages (questions or commands) to other
agents without needing to know the network details.

The Host Interface is responsible for routing the message to the correct
destination.

Potential Functions:
- ask(target_agent_id, question)
- execute(target_agent_id, command, params)
"""

class AgentCommunicator:
    def __init__(self, host_interface):
        """
        The communicator is given a reference to its host interface to
        handle the actual message sending.
        """
        self.host_interface = host_interface

    def ask(self, target_agent_id: str, question: str) -> str:
        """
        Sends a question to another agent and returns the response.
        """
        # This would call a method on the host interface, which then
        # handles the gRPC call if the target is in another instance.
        return self.host_interface.send_message(
            target=target_agent_id,
            message_type='ask',
            payload=question
        )

    def execute(self, target_agent_id: str, command: str, params: dict) -> dict:
        """
        Sends a command to another agent and returns the result.
        """
        return self.host_interface.send_message(
            target=target_agent_id,
            message_type='execute',
            payload={"command": command, "params": params}
        )
