import React, { useState } from 'react';
import {
  Bot,
  Lock,
  Unlock,
  Terminal,
  CheckCircle2,
  FileCode,
  Play,
  Sparkles,
  ShieldAlert,
  Clock,
  Layers,
} from 'lucide-react';
import { AgentInfo } from '../types';
import { Button } from '../components/common/Button';

interface AgentSwarmViewProps {
  agents: AgentInfo[];
  onTriggerAgentTask: (agentId: string) => void;
}

export const AgentSwarmView: React.FC<AgentSwarmViewProps> = ({
  agents,
  onTriggerAgentTask,
}) => {
  const [selectedAgentId, setSelectedAgentId] = useState<string>(agents[0]?.id || '');
  const [runningAgentId, setRunningAgentId] = useState<string | null>(null);
  const [consoleOutput, setConsoleOutput] = useState<string | null>(null);

  const selectedAgent = agents.find((a) => a.id === selectedAgentId) || agents[0];

  const handleRunAgentVerification = (agent: AgentInfo) => {
    setRunningAgentId(agent.id);
    setConsoleOutput(`Running agent verify command: ${agent.verifyCmd}...\nAllocating test runner container...`);

    setTimeout(() => {
      setConsoleOutput(
        `> ${agent.verifyCmd}\n` +
        `[OK] Loaded application context: ApplicationContext(db_pool=Pool(size=20), bot_client=Active)\n` +
        `[OK] Scope: ${agent.ownedFiles.join(', ')}\n` +
        `[OK] Pytest session started -- platform linux, Python 3.12.8, pytest-8.3.4\n` +
        `[OK] 142 passed, 0 skipped, 0 failed in 1.48s\n` +
        `[OK] Bandit scan: 0 High, 0 Medium findings in owned scope.\n` +
        `[SUCCESS] Verification passed for ${agent.name}! Safe to commit.`
      );
      setRunningAgentId(null);
      onTriggerAgentTask(agent.id);
    }, 900);
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-1.5 rounded-lg bg-sky-500/10 text-sky-400 border border-sky-500/20">
              <Bot className="w-5 h-5" />
            </span>
            <h2 className="text-xl font-bold text-white tracking-tight">
              Autonomous Agent Swarm (9 Subagents)
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Specialized engineering agents with strict file ownership, lock coordination &amp; preflight gates
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1.5 rounded-lg flex items-center gap-1.5">
            <Layers className="w-4 h-4" />
            Coordinator: Antigravity OS
          </span>
        </div>
      </div>

      {/* Main Grid: Agent Cards List & Selected Agent Detail Console */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Agents Grid */}
        <div className="lg:col-span-2 grid grid-cols-1 sm:grid-cols-2 gap-4">
          {agents.map((agent) => {
            const isSelected = agent.id === selectedAgent.id;
            const isRunning = runningAgentId === agent.id;

            return (
              <div
                key={agent.id}
                onClick={() => setSelectedAgentId(agent.id)}
                className={`p-4 rounded-xl border transition-all cursor-pointer flex flex-col justify-between ${
                  isSelected
                    ? 'bg-slate-900 border-amberline shadow-md'
                    : 'bg-slate-900/60 border-slate-800/80 hover:bg-slate-800/40 hover:border-slate-700'
                }`}
              >
                <div>
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <div className="p-1.5 rounded-lg bg-slate-800 text-amberline">
                        <Bot className="w-4 h-4" />
                      </div>
                      <div>
                        <h3 className="text-sm font-bold text-slate-100">{agent.name}</h3>
                        <p className="text-xs text-slate-400">{agent.role}</p>
                      </div>
                    </div>

                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded-full flex items-center gap-1 ${
                        agent.lockStatus === 'locked'
                          ? 'bg-amber-500/15 text-amberline border border-amber-500/30'
                          : 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                      }`}
                    >
                      {agent.lockStatus === 'locked' ? (
                        <>
                          <Lock className="w-3 h-3" /> Locked
                        </>
                      ) : (
                        <>
                          <Unlock className="w-3 h-3" /> Idle
                        </>
                      )}
                    </span>
                  </div>

                  <p className="text-xs text-slate-300 line-clamp-2 mt-2 leading-relaxed">
                    {agent.mission}
                  </p>

                  <div className="mt-3 flex flex-wrap gap-1">
                    {agent.ownedFiles.slice(0, 2).map((file, idx) => (
                      <span
                        key={idx}
                        className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-950 text-slate-400 border border-slate-800 truncate max-w-[180px]"
                      >
                        {file}
                      </span>
                    ))}
                    {agent.ownedFiles.length > 2 && (
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-950 text-slate-500 border border-slate-800">
                        +{agent.ownedFiles.length - 2} more
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex items-center justify-between pt-3 mt-3 border-t border-slate-800/60">
                  <span className="text-[11px] font-mono text-emerald-400 flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" /> Ready
                  </span>

                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleRunAgentVerification(agent);
                    }}
                    disabled={isRunning}
                    className="text-xs px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-md transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline flex items-center gap-1.5 active:scale-95"
                  >
                    <Play className="w-3 h-3 text-amberline" />
                    <span>Verify</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        {/* Right Column: Selected Agent Deep Dive & Simulated Terminal Output */}
        <div className="space-y-6">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <FileCode className="w-4 h-4 text-amberline" />
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                  Agent Specification
                </h3>
              </div>
              <span className="text-xs font-mono text-slate-400">
                {selectedAgent.id}
              </span>
            </div>

            <div className="space-y-2">
              <h4 className="text-base font-bold text-slate-100">
                {selectedAgent.name}
              </h4>
              <p className="text-xs text-slate-300 leading-relaxed bg-slate-950/60 p-3 rounded-lg border border-slate-800">
                {selectedAgent.mission}
              </p>
            </div>

            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 block mb-1.5">
                Owned Scope &amp; Files
              </span>
              <ul className="space-y-1 font-mono text-xs text-slate-300" aria-label="Owned files">
                {selectedAgent.ownedFiles.map((file, idx) => (
                  <li key={idx} className="p-1.5 bg-slate-950 rounded border border-slate-800/80 flex items-center gap-2">
                    <span className="text-amberline">•</span>
                    <span className="truncate">{file}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 block mb-1.5">
                Verification Command
              </span>
              <div className="p-2.5 bg-slate-950 border border-slate-800 rounded font-mono text-xs text-emerald-400 select-all">
                {selectedAgent.verifyCmd}
              </div>
            </div>

            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 block mb-1.5">
                Recent Completed Tasks
              </span>
              <ul className="space-y-1 text-xs text-slate-300" aria-label="Recent completed tasks">
                {selectedAgent.recentTasks.map((task, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                    <span>{task}</span>
                  </li>
                ))}
              </ul>
            </div>

            <Button
              variant="primary"
              size="md"
              className="w-full"
              isLoading={runningAgentId === selectedAgent.id}
              icon={<Play className="w-4 h-4" />}
              onClick={() => handleRunAgentVerification(selectedAgent)}
            >
              Execute {selectedAgent.name} Verification
            </Button>
          </div>

          {/* Simulated Console Stream */}
          {consoleOutput && (
            <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 font-mono text-xs text-slate-300 space-y-1 animate-fade-in shadow-inner">
              <div className="flex items-center justify-between text-slate-500 pb-2 border-b border-slate-800 text-[11px]">
                <span className="flex items-center gap-1.5">
                  <Terminal className="w-3.5 h-3.5 text-amberline" />
                  Terminal Output
                </span>
                <span className="text-emerald-400">Exit 0</span>
              </div>
              <pre className="whitespace-pre-wrap leading-relaxed text-[11px] pt-2 text-slate-200">
                {consoleOutput}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
