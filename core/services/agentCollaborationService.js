// backend/services/agentCollaborationService.js

const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();
const OpenRouterProvider = require('./openRouterProvider');
const amqp = require('amqplib');

class AgentCollaborationService {
  constructor(io) {
    this.io = io; // Socket.io instance
    this.openRouterProvider = OpenRouterProvider;
    this.channel = null; // RabbitMQ channel
    this.initRabbitMQ();
  }

  async initRabbitMQ() {
    try {
      const connection = await amqp.connect(process.env.RABBITMQ_URL || 'amqp://localhost');
      this.channel = await connection.createChannel();
      await this.channel.assertQueue('agent_messages', { durable: true });
      await this.channel.assertQueue('agent_responses', { durable: true });
      console.log('Connected to RabbitMQ');

      // Start consuming agent responses
      this.channel.consume('agent_responses', async (msg) => {
        if (msg !== null) {
          const responseData = JSON.parse(msg.content.toString());
          console.log('Received agent response from RabbitMQ:', responseData);

          const { channelId, senderId, content, threadId, originalMessageId } = responseData;

          // Store the agent's response in the database
          const agentResponse = await prisma.agentMessage.create({
            data: {
              channelId,
              senderId,
              senderType: 'agent',
              content,
              threadId: threadId || originalMessageId, // Use threadId if present, else original message
            },
          });

          // Emit the agent's response via Socket.io
          this.io.of('/workspace').to(channelId).emit('agent:message', agentResponse);
          this.io.of('/workspace').to(channelId).emit('agent:typing', {
            agentId: senderId,
            isTyping: false,
          });

          this.channel.ack(msg);
        }
      });

    } catch (error) {
      console.error('Failed to connect to RabbitMQ:', error);
    }
  }

  async handleUserMessage(messageData, userId) {
    const { channelId, content, threadId } = messageData;

    try {
      const newMessage = await prisma.agentMessage.create({
        data: {
          channelId,
          senderId: userId,
          senderType: 'user',
          content,
          threadId,
        },
      });

      this.io.of('/workspace').to(channelId).emit('agent:message', newMessage);

      // Check for @mentions and publish to RabbitMQ for AI agent processing
      if (content.text && content.text.includes('@')) {
        const mentionedAgentName = content.text.split('@')[1]?.split(' ')[0];
        if (mentionedAgentName) {
          const mentionedAgent = await prisma.customAgent.findFirst({
            where: { name: { contains: mentionedAgentName, mode: 'insensitive' } },
          });

          if (mentionedAgent && this.channel) {
            // Simulate typing
            this.io.of('/workspace').to(channelId).emit('agent:typing', {
              agentId: mentionedAgent.id,
              isTyping: true,
            });

            const messageForAgent = {
              originalMessageId: newMessage.id,
              channelId: channelId,
              agentId: mentionedAgent.id,
              agentName: mentionedAgent.name,
              userMessage: content.text,
              systemPrompt: mentionedAgent.systemPrompt,
              model: mentionedAgent.model,
              temperature: mentionedAgent.temperature,
              maxTokens: mentionedAgent.maxTokens,
              topP: mentionedAgent.topP,
              threadId: threadId,
            };

            this.channel.sendToQueue(
              'agent_messages',
              Buffer.from(JSON.stringify(messageForAgent)),
              { persistent: true }
            );
            console.log('Published message to agent_messages queue:', messageForAgent);
          } else if (!this.channel) {
            console.warn('RabbitMQ channel not available. Agent message not sent to queue.');
          }
        }
      }
    } catch (error) {
      console.error('Error handling user message in AgentCollaborationService:', error);
      throw new Error('Failed to process message');
    }
  }

  // This method will now be called by the agent consumer (e.g., a separate worker process)
  // that receives messages from RabbitMQ.
  async generateAgentResponse(agent, userMessage, systemPrompt, model, temperature, maxTokens, topP) {
    const prompt = `${systemPrompt}\n\nUser: ${userMessage}`;
    try {
      const response = await this.openRouterProvider.generateCompletion(
        prompt,
        model,
        {
          temperature,
          maxTokens,
          topP,
        }
      );
      return response;
    } catch (error) {
      console.error('Error generating agent response:', error);
      return `Sorry, I encountered an error while processing your request: ${error.message}`;
    }
  }

  // Other methods for agent-to-agent communication, slash commands, etc.
  // will be added here.
}

module.exports = AgentCollaborationService;