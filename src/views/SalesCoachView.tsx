import React, { useState } from 'react';
import {
  PhoneCall,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  Clock,
  User,
  Headphones,
  TrendingUp,
  Award,
  ChevronRight,
  Plus,
} from 'lucide-react';
import { SalesCallRecord, CallTranscriptLine } from '../types';
import { CallRecordingPlayer } from '../components/salescoach/CallRecordingPlayer';
import { Button } from '../components/common/Button';

interface SalesCoachViewProps {
  calls: SalesCallRecord[];
  onAddCallRecord: (call: SalesCallRecord) => void;
}

export const SalesCoachView: React.FC<SalesCoachViewProps> = ({
  calls,
  onAddCallRecord,
}) => {
  const [selectedCallId, setSelectedCallId] = useState<string>(calls[0]?.id || '');
  const [currentTime, setCurrentTime] = useState<number>(15);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [isSimulatingCall, setIsSimulatingCall] = useState<boolean>(false);

  const activeCall = calls.find((c) => c.id === selectedCallId) || calls[0];

  const handleSelectCall = (call: SalesCallRecord) => {
    setSelectedCallId(call.id);
    setCurrentTime(0);
    setIsPlaying(false);
  };

  const handleSeekToTranscriptLine = (line: CallTranscriptLine) => {
    setCurrentTime(line.seconds);
    setIsPlaying(true);
  };

  // Simulate analyzing a new incoming call recording
  const handleSimulateNewCall = () => {
    setIsSimulatingCall(true);
    setTimeout(() => {
      const newCall: SalesCallRecord = {
        id: `call-${Math.floor(100 + Math.random() * 900)}`,
        leadName: 'Bekzod Mirzayev (Express Delivery)',
        phone: '+998 90 999 77 11',
        operatorName: 'Dilnoza Karimova',
        durationSeconds: 165,
        audioDurationFormatted: '02:45',
        callDate: new Date().toISOString().replace('T', ' ').substring(0, 16),
        overallScore: 91,
        scriptAdherence: 95,
        empathyScore: 88,
        objectionHandlingScore: 90,
        dealOutcome: 'Won',
        dealValue: 15000000,
        coachingSummary: 'Ideal muloqot! Operator mijozning texnik savollariga (AmoCRM API va webhook latency) professional darajada javob berdi va darhol 15 mln so\'mlik shartnomani yopdi.',
        positivePoints: [
          'Kirish so\'zlarida mijoz ismini to\'g\'ri talaffuz qildi',
          'AmoCRM va CAPI integratsiyasi bo\'yicha aniq muddat va kafolat berdi',
          'Mijozning shubhalarini xushmuomalalik bilan bartaraf etdi',
        ],
        areasForImprovement: [
          'Kompaniya taqdimot faylini yuborishni unutmang',
        ],
        transcript: [
          { id: 'sim-1', speaker: 'operator', text: 'Assalomu alaykum Bekzod aka! Oisha OS integratsiya bo\'limidan Dilnoza bo\'laman.', timestamp: '00:04', seconds: 4, sentiment: 'positive' },
          { id: 'sim-2', speaker: 'client', text: 'Salom Dilnoza. Bizga AmoCRM bilan Telegram guruhimizni bog\'laydigan va CAPI ga to\'g\'ri uzatadigan tizim kerak edi.', timestamp: '00:14', seconds: 14, sentiment: 'neutral' },
          { id: 'sim-3', speaker: 'operator', text: 'Aynan shunday. Oisha OS da barcha Meta CAPI hodisalari SHA-256 bilan himoyalanadi va CRM ga real-time tushadi.', timestamp: '00:32', seconds: 32, sentiment: 'positive' },
          { id: 'sim-4', speaker: 'client', text: 'Bu juda ajoyib. Bugun ulanishni boshlay olamizmi?', timestamp: '00:55', seconds: 55, sentiment: 'positive' },
          { id: 'sim-5', speaker: 'operator', text: 'Ha, albatta. Hozir shartnomani jo\'nataman va Hisobchi AI botimiz billing qilib beradi.', timestamp: '01:15', seconds: 75, sentiment: 'positive' },
        ],
      };

      onAddCallRecord(newCall);
      setSelectedCallId(newCall.id);
      setCurrentTime(0);
      setIsSimulatingCall(false);
    }, 1200);
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-1.5 rounded-lg bg-amber-500/10 text-amberline border border-amber-500/20">
              <Headphones className="w-5 h-5" />
            </span>
            <h2 className="text-xl font-bold text-white tracking-tight">
              SalesCoach AI • Speech Intelligence
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Call recording playback, script adherence evaluation & automated sales coaching
          </p>
        </div>

        <Button
          variant="primary"
          size="sm"
          isLoading={isSimulatingCall}
          icon={<Plus className="w-4 h-4" />}
          onClick={handleSimulateNewCall}
        >
          Analyze New Call Recording
        </Button>
      </div>

      {/* Main Grid: Left Call Selector & Right Player + Transcript */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Call List */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-sm flex flex-col space-y-3">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
              Recorded Sales Calls ({calls.length})
            </h3>
            <span className="text-[11px] font-mono text-slate-500">Audio + NLP</span>
          </div>

          <ul className="space-y-2 overflow-y-auto max-h-[600px]" aria-label="Recorded sales calls list">
            {calls.map((call) => {
              const isSelected = call.id === activeCall.id;
              return (
                <li key={call.id}>
                  <button
                    type="button"
                    onClick={() => handleSelectCall(call)}
                    aria-current={isSelected ? 'true' : undefined}
                    className={`w-full p-3 rounded-lg text-left transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline border ${
                      isSelected
                        ? 'bg-amber500/10 bg-slate-800/80 border-amberline/50 text-white shadow-sm'
                        : 'bg-slate-950/60 border-slate-800/80 text-slate-300 hover:bg-slate-800/40 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-slate-200 truncate">
                        {call.leadName}
                      </span>
                      <span
                        className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded ${
                          call.overallScore >= 80
                            ? 'bg-emerald-500/20 text-emerald-400'
                            : 'bg-amber-500/20 text-amberline'
                        }`}
                      >
                        {call.overallScore}%
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-xs text-slate-400 mt-2">
                      <span className="flex items-center gap-1 truncate">
                        <User className="w-3 h-3 text-slate-500" />
                        {call.operatorName}
                      </span>
                      <span className="flex items-center gap-1 font-mono text-[11px]">
                        <Clock className="w-3 h-3 text-slate-500" />
                        {call.audioDurationFormatted}
                      </span>
                    </div>

                    <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-800/60 text-[11px]">
                      <span className="text-slate-500 font-mono">{call.callDate}</span>
                      <span
                        className={`font-semibold ${
                          call.dealOutcome === 'Won'
                            ? 'text-emerald-400'
                            : call.dealOutcome === 'Follow-up'
                            ? 'text-amberline'
                            : 'text-slate-400'
                        }`}
                      >
                        {call.dealOutcome}
                      </span>
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>

        {/* Right 2 cols: Accessible Audio Player & Coaching Scorecard */}
        <div className="lg:col-span-2 space-y-6">
          {/* Accessible Audio Player Component */}
          {activeCall && (
            <CallRecordingPlayer
              call={activeCall}
              currentTime={currentTime}
              onTimeUpdate={setCurrentTime}
              isPlaying={isPlaying}
              onPlayPauseToggle={() => setIsPlaying(!isPlaying)}
            />
          )}

          {/* Coaching Scorecards */}
          {activeCall && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
                <span className="text-xs text-slate-400">Overall Score</span>
                <p className="text-2xl font-bold font-mono text-amberline mt-1">
                  {activeCall.overallScore}%
                </p>
                <span className="text-[10px] text-slate-500">Benchmark: 80%</span>
              </div>

              <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
                <span className="text-xs text-slate-400">Script Adherence</span>
                <p className="text-2xl font-bold font-mono text-emerald-400 mt-1">
                  {activeCall.scriptAdherence}%
                </p>
                <span className="text-[10px] text-slate-500">Step checklist met</span>
              </div>

              <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
                <span className="text-xs text-slate-400">Empathy &amp; Tone</span>
                <p className="text-2xl font-bold font-mono text-sky-400 mt-1">
                  {activeCall.empathyScore}%
                </p>
                <span className="text-[10px] text-slate-500">Active listening</span>
              </div>

              <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
                <span className="text-xs text-slate-400">Objection Handling</span>
                <p className="text-2xl font-bold font-mono text-purple-400 mt-1">
                  {activeCall.objectionHandlingScore}%
                </p>
                <span className="text-[10px] text-slate-500">Price &amp; Timing</span>
              </div>
            </div>
          )}

          {/* AI Coaching Summary & Takeaways */}
          {activeCall && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-amberline" />
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                  AI SalesCoach Evaluation
                </h3>
              </div>

              <p className="text-xs sm:text-sm text-slate-300 leading-relaxed bg-slate-950/60 p-3.5 rounded-lg border border-slate-800">
                {activeCall.coachingSummary}
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
                {/* Visual anchors checkmark pattern as specified in .Jules/palette.md line 44:
                    "Enhance plain text list items with subtle visual anchors, such as an inline SVG checkmark with flex items-center gap-3" */}
                <div>
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-emerald-400 mb-2">
                    Muvaffaqiyatli jihatlar (Key Wins)
                  </h4>
                  <ul className="space-y-2 text-xs text-slate-300" aria-label="Positive coaching highlights">
                    {activeCall.positivePoints.map((point, idx) => (
                      <li key={idx} className="flex items-start gap-3">
                        <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" aria-hidden="true" />
                        <span>{point}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div>
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-amberline mb-2">
                    Yaxshilash zonalari (Actionable Tips)
                  </h4>
                  <ul className="space-y-2 text-xs text-slate-300" aria-label="Improvement points">
                    {activeCall.areasForImprovement.map((point, idx) => (
                      <li key={idx} className="flex items-start gap-3">
                        <AlertCircle className="w-4 h-4 text-amberline shrink-0 mt-0.5" aria-hidden="true" />
                        <span>{point}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}

          {/* Synchronized Diarized Transcript */}
          {activeCall && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2">
                  <PhoneCall className="w-4 h-4 text-amberline" />
                  <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                    Diarized Speech Transcript
                  </h3>
                </div>
                <span className="text-xs text-slate-500">
                  Click any line to jump audio
                </span>
              </div>

              <div className="space-y-3 max-h-80 overflow-y-auto pr-1">
                {activeCall.transcript.map((line) => {
                  const isCurrent =
                    currentTime >= line.seconds &&
                    currentTime < line.seconds + 15;
                  const isOperator = line.speaker === 'operator';

                  return (
                    <div
                      key={line.id}
                      onClick={() => handleSeekToTranscriptLine(line)}
                      className={`p-3 rounded-xl border transition-all cursor-pointer ${
                        isCurrent
                          ? 'bg-amberline/10 border-amberline/50 shadow-sm'
                          : 'bg-slate-950/60 border-slate-800/80 hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1.5">
                        <div className="flex items-center gap-2">
                          <span
                            className={`text-[11px] font-bold px-2 py-0.5 rounded ${
                              isOperator
                                ? 'bg-amber-500/20 text-amberline'
                                : 'bg-sky-500/20 text-sky-400'
                            }`}
                          >
                            {isOperator ? 'Operator (Dilnoza)' : 'Client (Mijoz)'}
                          </span>
                          {line.sentiment === 'objection' && (
                            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-400 border border-rose-500/30">
                              Objection Handled
                            </span>
                          )}
                        </div>
                        <button
                          type="button"
                          aria-label={`Jump audio to ${line.timestamp}`}
                          className="text-xs font-mono text-slate-500 hover:text-amberline transition-colors"
                        >
                          {line.timestamp}
                        </button>
                      </div>
                      <p className="text-xs sm:text-sm text-slate-200 leading-relaxed">
                        {line.text}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
