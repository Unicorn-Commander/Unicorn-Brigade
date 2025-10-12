import { motion } from 'framer-motion';
import { Bot, User } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

const ChatMessage = ({ message }) => {
  const isUser = message.role === 'user';

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
    >
      <div className={`flex items-start space-x-3 max-w-2xl ${isUser ? 'flex-row-reverse space-x-reverse' : ''}`}>
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
          isUser ? 'bg-gradient-to-br from-cyan-500 to-blue-500' : 'bg-gradient-to-br from-unicorn-500 to-purple-500'
        }`}>
          {isUser ? <User className="w-5 h-5 text-white" /> : <Bot className="w-5 h-5 text-white" />}
        </div>

        <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
          {!isUser && message.agent && (
            <span className="text-xs text-slate-500 mb-1">{message.agent.name}</span>
          )}

          <div className={`rounded-lg px-4 py-3 ${
            isUser ? 'bg-cyan-500/20 border border-cyan-500/30' : 'glass'
          }`}>
            <ReactMarkdown
              className="prose prose-invert prose-sm max-w-none"
              components={{
                code({ node, inline, className, children, ...props }) {
                  const match = /language-(\w+)/.exec(className || '');
                  return !inline && match ? (
                    <SyntaxHighlighter
                      style={oneDark}
                      language={match[1]}
                      PreTag="div"
                      {...props}
                    >
                      {String(children).replace(/\n$/, '')}
                    </SyntaxHighlighter>
                  ) : (
                    <code className="bg-slate-800 px-1 py-0.5 rounded text-cyan-400" {...props}>
                      {children}
                    </code>
                  );
                }
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>

          <span className="text-xs text-slate-600 mt-1">
            {new Date(message.timestamp).toLocaleTimeString()}
          </span>
        </div>
      </div>
    </motion.div>
  );
};

export default ChatMessage;