'use client';

import { useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { Play, Pause, Repeat, Loader2, Volume2, ChevronDown, ChevronUp } from 'lucide-react';
import { useI18n } from '@/lib/hooks/use-i18n';
import { AvatarDisplay } from '@/components/ui/avatar-display';
import type { AudioIndicatorState } from '@/components/roundtable/audio-indicator';
import type { PlaybackView } from '@/lib/playback';
import type { Participant } from '@/lib/types/roundtable';
import { cn } from '@/lib/utils';
import { DEFAULT_TEACHER_AVATAR, DEFAULT_STUDENT_AVATAR } from '@/components/roundtable/constants';

const PRESENTATION_BUBBLE_WIDTH = 'w-[min(420px,calc(100vw-3rem))]';

interface PresentationSpeechOverlayProps {
  readonly playbackView: PlaybackView;
  readonly participants: Participant[];
  readonly speakingAgentId: string | null;
  readonly isTopicPending: boolean;
  readonly userAvatar?: string;
  /** Which side this overlay instance renders — 'left' or 'right' */
  readonly side?: 'left' | 'right';
  readonly onBubbleClick?: () => void;
  readonly audioIndicatorState?: AudioIndicatorState;
  readonly buttonState?: 'play' | 'bars' | 'restart' | 'none';
  readonly isPaused?: boolean;
}

export interface PresentationBubbleModel {
  key: string;
  role: 'teacher' | 'agent' | 'user';
  side: 'left' | 'right';
  name: string;
  avatar: string;
  text: string;
  isLoading: boolean;
  isTopicPending: boolean;
}

export function buildPresentationBubbleModel({
  playbackView,
  participants,
  speakingAgentId,
  isTopicPending,
  fallbackTeacherName,
  fallbackStudentName,
  fallbackUserName,
  userAvatar,
}: {
  playbackView: PlaybackView;
  participants: Participant[];
  speakingAgentId: string | null;
  isTopicPending: boolean;
  fallbackTeacherName: string;
  fallbackStudentName: string;
  fallbackUserName: string;
  userAvatar?: string;
}): PresentationBubbleModel | null {
  const { phase, bubbleRole, sourceText } = playbackView;
  const showDuringPhase =
    phase === 'lecturePlaying' ||
    phase === 'lecturePaused' ||
    phase === 'discussionActive' ||
    phase === 'discussionPaused';
  const isLoading = phase === 'discussionActive' && bubbleRole !== null && sourceText === '';

  if (!showDuringPhase) return null;
  if (bubbleRole !== 'teacher' && bubbleRole !== 'agent' && bubbleRole !== 'user') return null;
  if (!sourceText && !isLoading) return null;

  const teacherParticipant = participants.find((participant) => participant.role === 'teacher');
  const speakingStudent = speakingAgentId
    ? participants.find(
        (participant) =>
          participant.id === speakingAgentId &&
          participant.role !== 'teacher' &&
          participant.role !== 'user',
      )
    : null;

  if (bubbleRole === 'teacher') {
    return {
      key: 'teacher',
      role: 'teacher',
      side: 'left',
      name: teacherParticipant?.name || fallbackTeacherName,
      avatar: teacherParticipant?.avatar || DEFAULT_TEACHER_AVATAR,
      text: sourceText,
      isLoading,
      isTopicPending,
    };
  }

  if (bubbleRole === 'user') {
    const userParticipant = participants.find((p) => p.role === 'user');
    return {
      key: 'user',
      role: 'user',
      side: 'right',
      name: userParticipant?.name || fallbackUserName,
      avatar: userAvatar || userParticipant?.avatar || DEFAULT_STUDENT_AVATAR,
      text: sourceText,
      isLoading,
      isTopicPending,
    };
  }

  return {
    key: `agent-${speakingAgentId || 'unknown'}`,
    role: 'agent',
    side: 'right',
    name: speakingStudent?.name || fallbackStudentName,
    avatar: speakingStudent?.avatar || DEFAULT_STUDENT_AVATAR,
    text: sourceText,
    isLoading,
    isTopicPending,
  };
}

/** Collapsed pill — shows avatar + name, click to expand */
function CollapsedBubblePill({
  bubble,
  onExpand,
  onPlayPause,
  isPaused,
}: {
  readonly bubble: PresentationBubbleModel;
  readonly onExpand: () => void;
  readonly onPlayPause?: () => void;
  readonly isPaused?: boolean;
}) {
  return (
    <div className="flex items-center gap-2" onClick={onExpand}>
      <div
        className={cn(
          'flex items-center gap-2 px-3 py-1.5 rounded-full border backdrop-blur-xl shadow-md cursor-pointer transition-all duration-200',
          'hover:shadow-lg hover:scale-[1.02] active:scale-[0.98]',
          'bg-card/90 text-foreground border-border',
        )}
      >
        <div
          className={cn(
            'w-6 h-6 rounded-full overflow-hidden border border-border shrink-0',
          )}
        >
          <AvatarDisplay src={bubble.avatar} alt={bubble.name} />
        </div>
        <span className="text-xs font-medium text-foreground truncate max-w-[120px]">
          {bubble.name}
        </span>
        <ChevronUp className="w-3 h-3 text-muted-foreground shrink-0" />
      </div>
      {onPlayPause && (
        <div
          onClick={(e) => {
            e.stopPropagation();
            onPlayPause();
          }}
          className={cn(
            'p-2 rounded-full border backdrop-blur-xl shadow-md cursor-pointer transition-all duration-200',
            'hover:shadow-lg hover:scale-[1.02] active:scale-[0.98]',
            'bg-card/90 border-border hover:bg-muted',
          )}
        >
          {isPaused ? (
            <Play className="w-3.5 h-3.5 text-muted-foreground ml-0.5" />
          ) : (
            <Pause className="w-3.5 h-3.5 text-muted-foreground" />
          )}
        </div>
      )}
    </div>
  );
}

/** Reusable bubble card — renders the speech bubble content (avatar, name, text) */
export function PresentationBubbleCard({
  bubble,
  onClick,
  onCollapse,
  audioIndicatorState,
  buttonState,
  isPaused,
}: {
  readonly bubble: PresentationBubbleModel;
  readonly onClick?: () => void;
  readonly onCollapse?: () => void;
  readonly audioIndicatorState?: AudioIndicatorState;
  readonly buttonState?: 'play' | 'bars' | 'restart' | 'none';
  readonly isPaused?: boolean;
}) {
  const { t } = useI18n();
  return (
    <div
      aria-live="polite"
      onClick={onClick}
      className={cn(
        'relative w-full min-w-0 rounded-3xl border border-border backdrop-blur-xl shadow-[0_18px_50px_-20px_rgba(0,0,0,0.45)] overflow-hidden group/bubble bg-card/95 text-card-foreground',
        onClick && 'cursor-pointer',
      )}
    >
      <div className="flex items-center gap-3 px-4 pt-3 pb-2">
        <div
          className={cn(
            'w-10 h-10 rounded-full overflow-hidden border border-border shadow-sm shrink-0',
          )}
        >
          <AvatarDisplay src={bubble.avatar} alt={bubble.name} />
        </div>
        <div className="min-w-0">
          <div
            className={cn(
              'text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground',
            )}
          >
            {bubble.role === 'user'
              ? t('roundtable.you')
              : bubble.role === 'agent'
                ? t('settings.agentRoles.student')
                : t('settings.agentRoles.teacher')}
          </div>
          <div className="flex items-center gap-1.5">
            <div className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
              {bubble.name}
            </div>
            {audioIndicatorState === 'generating' && (
              <Loader2 className="w-3.5 h-3.5 text-amber-500 dark:text-amber-400 animate-spin" />
            )}
            {audioIndicatorState === 'playing' && (
              <Volume2 className="w-3.5 h-3.5 text-gray-500 dark:text-gray-400" />
            )}
          </div>
        </div>
        {onCollapse && (
          <div
            onClick={(e) => {
              e.stopPropagation();
              onCollapse();
            }}
            className="absolute top-2 right-2 p-1.5 rounded-full text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100/80 dark:hover:bg-gray-800/80 transition-colors duration-200 cursor-pointer z-10"
          >
            <ChevronDown className="w-4 h-4" />
          </div>
        )}
      </div>

      <div className="ml-4 mr-10 mb-4 max-h-[140px] overflow-y-auto scrollbar-hide">
        {bubble.isLoading ? (
          <div className="flex gap-1 items-center py-1">
            {[0, 0.2, 0.4].map((delay) => (
              <motion.div
                key={delay}
                animate={{ opacity: [0.3, 1, 0.3] }}
                transition={{ repeat: Infinity, duration: 1, delay }}
                className={cn(
                  'w-1.5 h-1.5 rounded-full',
                  bubble.role === 'user'
                    ? 'bg-violet-400 dark:bg-violet-500'
                    : 'bg-foreground/40 dark:bg-foreground/40',
                )}
              />
            ))}
          </div>
        ) : (
          <p className="text-[15px] leading-relaxed whitespace-pre-wrap break-words text-foreground">
            {bubble.text}
            {bubble.isTopicPending && (
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-red-500 ml-1 align-middle" />
            )}
          </p>
        )}
      </div>

      {bubble.role !== 'user' &&
        !bubble.isLoading &&
        buttonState &&
        buttonState !== 'none' &&
        (() => {
          const barsColor = 'currentColor';

          if (buttonState === 'play') {
            return (
              <div
                onClick={(e) => {
                  e.stopPropagation();
                  onClick?.();
                }}
                className="absolute right-2.5 bottom-2.5 z-20 p-1.5 rounded-full bg-card/80 backdrop-blur-sm group-hover/bubble:bg-muted transition-all duration-300 cursor-pointer"
              >
                <Play className="w-3.5 h-3.5 text-muted-foreground group-hover/bubble:text-foreground ml-0.5" />
              </div>
            );
          }

          if (buttonState === 'restart') {
            return (
              <div
                onClick={(e) => {
                  e.stopPropagation();
                  onClick?.();
                }}
                className="absolute right-2.5 bottom-2.5 z-20 p-1.5 rounded-full bg-card/80 backdrop-blur-sm group-hover/bubble:bg-muted transition-all duration-300 cursor-pointer"
              >
                <Repeat className="w-3.5 h-3.5 text-muted-foreground group-hover/bubble:text-foreground" />
              </div>
            );
          }

          // buttonState === 'bars'
          return (
            <div
              onClick={(e) => {
                e.stopPropagation();
                onClick?.();
              }}
              className="absolute right-2.5 bottom-2.5 z-20 p-1.5 rounded-full bg-card/80 backdrop-blur-sm group-hover/bubble:bg-muted transition-all duration-300 cursor-pointer"
            >
              {isPaused ? (
                <Play className="w-3.5 h-3.5 text-amber-500 dark:text-amber-400 group-hover/bubble:text-foreground ml-0.5" />
              ) : (
                <>
                  {/* Breathing bars — visible by default, hidden on hover */}
                  <div className="flex gap-0.5 items-end justify-center h-3.5 w-3.5 group-hover/bubble:hidden text-foreground">
                    <div
                      className="w-1 rounded-full"
                      style={{
                        backgroundColor: barsColor,
                        animation: 'breathing-bar-1 0.6s ease-in-out infinite',
                      }}
                    />
                    <div
                      className="w-1 rounded-full"
                      style={{
                        backgroundColor: barsColor,
                        animation: 'breathing-bar-2 0.4s ease-in-out infinite',
                      }}
                    />
                    <div
                      className="w-1 rounded-full"
                      style={{
                        backgroundColor: barsColor,
                        animation: 'breathing-bar-3 0.5s ease-in-out infinite',
                      }}
                    />
                  </div>
                  {/* Pause icon on hover */}
                  <Pause className="w-3.5 h-3.5 text-foreground hidden group-hover/bubble:block" />
                </>
              )}
            </div>
          );
        })()}
    </div>
  );
}

export function PresentationSpeechOverlay({
  playbackView,
  participants,
  speakingAgentId,
  isTopicPending,
  userAvatar,
  side = 'left',
  onBubbleClick,
  audioIndicatorState,
  buttonState,
  isPaused,
}: PresentationSpeechOverlayProps) {
  const { t } = useI18n();

  const bubble = buildPresentationBubbleModel({
    playbackView,
    participants,
    speakingAgentId,
    isTopicPending,
    fallbackTeacherName: t('roundtable.teacher'),
    fallbackStudentName: t('settings.agentRoles.student'),
    fallbackUserName: t('roundtable.you'),
    userAvatar,
  });

  // Persistent collapse: once collapsed, stay collapsed until user explicitly expands.
  // Left/right sides are separate component instances so they track independently.
  // Right-side agents share a single instance, so all agents share the same collapse state.
  const [isCollapsed, setIsCollapsed] = useState(false);

  const matchesSide = !!(bubble && bubble.side === side);

  const renderContent = (b: PresentationBubbleModel) => (
    <AnimatePresence mode="wait" initial={false}>
      {isCollapsed ? (
        <motion.div
          key="collapsed"
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.9 }}
          transition={{ duration: 0.18 }}
        >
          <CollapsedBubblePill
            bubble={b}
            onExpand={() => setIsCollapsed(false)}
            onPlayPause={onBubbleClick}
            isPaused={isPaused}
          />
        </motion.div>
      ) : (
        <motion.div
          key="expanded"
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          transition={{ duration: 0.18 }}
          className={PRESENTATION_BUBBLE_WIDTH}
        >
          <PresentationBubbleCard
            bubble={b}
            onClick={onBubbleClick}
            onCollapse={() => setIsCollapsed(true)}
            audioIndicatorState={audioIndicatorState}
            buttonState={buttonState}
            isPaused={isPaused}
          />
        </motion.div>
      )}
    </AnimatePresence>
  );

  /* ── Left-side overlay: suppressed to prevent invasive floating window in left bottom ── */
  if (side === 'left') {
    return null;
  }

  /* ── Right-side: inline flow, rendered inside the dock's flex column ── */
  return (
    <AnimatePresence mode="wait">
      {matchesSide && bubble && (
        <motion.div
          key={bubble.key}
          initial={{ opacity: 0, x: 20, y: 12 }}
          animate={{ opacity: 1, x: 0, y: 0 }}
          exit={{ opacity: 0, y: 8 }}
          transition={{ duration: 0.22, ease: [0.21, 1, 0.36, 1] }}
          className="pointer-events-auto"
        >
          {renderContent(bubble)}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
