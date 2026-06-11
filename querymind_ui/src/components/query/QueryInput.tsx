import { useRef, useEffect } from 'react';
import { Send, Loader2 } from 'lucide-react';

interface Props {
  question: string;
  setQuestion: (q: string) => void;
  onSubmit: () => void;
  loading: boolean;
}

export default function QueryInput({ question, setQuestion, onSubmit, loading }: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.max(120, textareaRef.current.scrollHeight)}px`;
    }
  }, [question]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && e.ctrlKey) {
      e.preventDefault();
      onSubmit();
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 flex flex-col">
        <label className="block text-xs font-medium text-slate-400 uppercase tracking-widest mb-3">
          Your Question
        </label>
        <textarea
          ref={textareaRef}
          value={question}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask anything about your database..."
          className="w-full bg-slate-900 border border-slate-700 rounded-xl p-4 text-slate-100 placeholder-slate-600
                     focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent
                     transition-all duration-200 text-sm resize-none leading-relaxed flex-1 min-h-[120px]"
          disabled={loading}
        />
        <p className="mt-2 text-xs text-slate-600">
          <kbd className="bg-slate-800 border border-slate-700 rounded px-1 py-0.5 text-slate-500">Ctrl</kbd>
          {' + '}
          <kbd className="bg-slate-800 border border-slate-700 rounded px-1 py-0.5 text-slate-500">↵</kbd>
          {' to submit'}
        </p>
      </div>

      <button
        onClick={onSubmit}
        disabled={loading || !question.trim()}
        className="btn-primary mt-4 flex items-center justify-center gap-2 w-full"
      >
        {loading ? (
          <><Loader2 size={16} className="animate-spin" /> Thinking...</>
        ) : (
          <><Send size={15} /> Ask QueryMind</>
        )}
      </button>
    </div>
  );
}
