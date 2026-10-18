import React, { useState, useEffect, useRef } from 'react';
import { Play, Pause, RotateCcw, RotateCw, Volume2, VolumeX, Sparkles } from 'lucide-react';
import { SalesCallRecord } from '../../types';

interface CallRecordingPlayerProps {
  call: SalesCallRecord;
  currentTime: number;
  onTimeUpdate: (seconds: number) => void;
  isPlaying: boolean;
  onPlayPauseToggle: () => void;
}

export const CallRecordingPlayer: React.FC<CallRecordingPlayerProps> = ({
  call,
  currentTime,
  onTimeUpdate,
  isPlaying,
  onPlayPauseToggle,
}) => {
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1);
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const totalDuration = call.durationSeconds || 180;
  const timerRef = useRef<number | null>(null);

  // Playback timer simulation
  useEffect(() => {
    if (isPlaying) {
      const intervalMs = 1000 / playbackSpeed;
      timerRef.current = window.setInterval(() => {
        onTimeUpdate(Math.min(totalDuration, currentTime + 1));
      }, intervalMs);
    } else if (timerRef.current) {
      clearInterval(timerRef.current);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isPlaying, currentTime, playbackSpeed, totalDuration, onTimeUpdate]);

  const handleRewind10 = () => {
    onTimeUpdate(Math.max(0, currentTime - 10));
  };

  const handleFastForward10 = () => {
    onTimeUpdate(Math.min(totalDuration, currentTime + 10));
  };

  const cycleSpeed = () => {
    const speeds = [1, 1.25, 1.5, 2];
    const nextIdx = (speeds.indexOf(playbackSpeed) + 1) % speeds.length;
    setPlaybackSpeed(speeds[nextIdx]);
  };

  const formatSeconds = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  // Generate pseudo waveform bars based on call duration
  const waveformBars = [
    30, 45, 60, 40, 80, 95, 70, 50, 65, 85, 90, 75, 40, 60, 80, 55, 30, 70, 85,
    95, 60, 40, 65, 80, 90, 100, 75, 50, 45, 60, 75, 90, 80, 55, 35, 60, 70, 45,
    30, 50, 65, 80, 60, 40, 70, 85, 90, 65, 45, 30,
  ];

  const currentPercent = (currentTime / totalDuration) * 100;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-lg flex flex-col gap-3">
      {/* Top row: Call meta & scores */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Call Recording Analyzer
          </span>
          <span className="text-xs font-mono text-slate-500">ID: {call.id}</span>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-amberline text-xs font-medium">
            <Sparkles className="w-3.5 h-3.5" />
            <span>AI Score: {call.overallScore}/100</span>
          </div>
          <span className="text-xs text-slate-400 font-mono">
            {formatSeconds(currentTime)} / {formatSeconds(totalDuration)}
          </span>
        </div>
      </div>

      {/* Waveform Visualization & Scrubber */}
      <div className="relative py-2">
        <div
          role="slider"
          tabIndex={0}
          aria-label="Call playback progress"
          aria-valuemin={0}
          aria-valuemax={totalDuration}
          aria-valuenow={currentTime}
          aria-valuetext={`${formatSeconds(currentTime)} of ${formatSeconds(totalDuration)}`}
          onKeyDown={(e) => {
            if (e.key === 'ArrowLeft') onTimeUpdate(Math.max(0, currentTime - 5));
            if (e.key === 'ArrowRight') onTimeUpdate(Math.min(totalDuration, currentTime + 5));
          }}
          onClick={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const clickPos = (e.clientX - rect.left) / rect.width;
            onTimeUpdate(Math.round(clickPos * totalDuration));
          }}
          className="relative h-12 flex items-center justify-between gap-1 cursor-pointer group focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline rounded-lg px-1"
        >
          {waveformBars.map((height, idx) => {
            const barPos = (idx / waveformBars.length) * 100;
            const isPlayed = barPos <= currentPercent;
            return (
              <div
                key={idx}
                style={{ height: `${height}%` }}
                className={`w-full rounded-sm transition-colors duration-100 ${
                  isPlayed
                    ? 'bg-amberline group-hover:bg-amber-400'
                    : 'bg-slate-800 group-hover:bg-slate-700'
                }`}
              />
            );
          })}

          {/* Progress Playhead Line */}
          <div
            style={{ left: `${currentPercent}%` }}
            className="absolute top-0 bottom-0 w-0.5 bg-amberline shadow-[0_0_8px_#d9922e] pointer-events-none"
          >
            <div className="w-2.5 h-2.5 -ml-1 rounded-full bg-amberline border-2 border-slate-950" />
          </div>
        </div>
      </div>

      {/* Accessible Player Controls */}
      <div className="flex items-center justify-between pt-1">
        <div className="flex items-center gap-2">
          {/* Rewind 10 seconds button with explicit aria-label */}
          <button
            type="button"
            onClick={handleRewind10}
            aria-label="Rewind call recording 10 seconds"
            className="p-2 text-slate-300 hover:text-white hover:bg-slate-800 rounded-lg transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline active:scale-95"
          >
            <RotateCcw className="w-4 h-4" />
          </button>

          {/* Play / Pause button with explicit aria-label */}
          <button
            type="button"
            onClick={onPlayPauseToggle}
            aria-label={isPlaying ? 'Pause call recording' : 'Play call recording'}
            className="p-2.5 bg-amberline hover:bg-amber-500 text-slate-950 rounded-full transition-all shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 active:scale-95"
          >
            {isPlaying ? (
              <Pause className="w-5 h-5 fill-current" />
            ) : (
              <Play className="w-5 h-5 fill-current ml-0.5" />
            )}
          </button>

          {/* Fast Forward 10 seconds button with explicit aria-label */}
          <button
            type="button"
            onClick={handleFastForward10}
            aria-label="Fast forward call recording 10 seconds"
            className="p-2 text-slate-300 hover:text-white hover:bg-slate-800 rounded-lg transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline active:scale-95"
          >
            <RotateCw className="w-4 h-4" />
          </button>
        </div>

        {/* Speed and Volume Controls */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={cycleSpeed}
            aria-label={`Change playback speed, currently ${playbackSpeed}x`}
            className="px-2 py-1 text-xs font-mono font-medium text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-md transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline active:scale-95"
          >
            {playbackSpeed}x
          </button>

          <button
            type="button"
            onClick={() => setIsMuted(!isMuted)}
            aria-label={isMuted ? 'Unmute recording audio' : 'Mute recording audio'}
            className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline active:scale-95"
          >
            {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
          </button>
        </div>
      </div>
    </div>
  );
};
