import {
  WebSocketGateway,
  WebSocketServer,
  SubscribeMessage,
  MessageBody,
  ConnectedSocket,
  OnGatewayConnection,
  OnGatewayDisconnect,
} from '@nestjs/websockets';
import { Logger } from '@nestjs/common';
import { Server, Socket } from 'socket.io';
import { NegotiationsService, RealtimeSuggestion } from '../negotiations/negotiations.service';
import { RealtimeSuggestionDto } from '../negotiations/dto/negotiate.dto';

/**
 * CoachingGateway — real-time WebSocket for live call coaching.
 *
 * Events emitted TO client:
 *   - "coaching:tip"       — RealtimeSuggestion (during live call)
 *   - "coaching:scorecard" — Final scorecard (after call ends)
 *   - "coaching:alert"     — Urgent risk flag detected
 *   - "call:status"        — Call processing status update
 *
 * Events received FROM client:
 *   - "call:join"          — Manager joins a call room
 *   - "call:transcript"    — Live transcript chunk from manager's device
 *   - "call:end"           — Signal call finished
 */
@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/coaching',
})
export class CoachingGateway implements OnGatewayConnection, OnGatewayDisconnect {
  @WebSocketServer()
  server!: Server;

  private readonly logger = new Logger(CoachingGateway.name);

  // Map: callId → Set<socketId>  (multiple managers can observe same call)
  private callRooms = new Map<string, Set<string>>();
  // Map: socketId → { orgId, managerId, callId }
  private connections = new Map<string, { orgId: string; managerId: string; callId: string | undefined }>();

  constructor(private negotiations: NegotiationsService) {}

  // ─────────────────────── Lifecycle ───────────────────────────────────────

  handleConnection(socket: Socket) {
    // Auth: expect ?token=<jwt> or Authorization header
    const managerId = (socket.handshake.query.managerId as string) ?? 'unknown';
    const orgId = (socket.handshake.query.orgId as string) ?? 'unknown';
    this.connections.set(socket.id, { orgId, managerId, callId: undefined });
    this.logger.log(`[WS] Connected: ${managerId} (${socket.id})`);
  }

  handleDisconnect(socket: Socket) {
    const meta = this.connections.get(socket.id);
    if (meta?.callId) {
      this.leaveCallRoom(socket.id, meta.callId);
    }
    this.connections.delete(socket.id);
    this.logger.log(`[WS] Disconnected: ${socket.id}`);
  }

  // ─────────────────────── Client → Server events ──────────────────────────

  @SubscribeMessage('call:join')
  handleJoinCall(
    @ConnectedSocket() socket: Socket,
    @MessageBody() data: { callId: string },
  ) {
    const meta = this.connections.get(socket.id);
    if (!meta) return;

    if (!this.callRooms.has(data.callId)) {
      this.callRooms.set(data.callId, new Set());
    }
    this.callRooms.get(data.callId)!.add(socket.id);
    meta.callId = data.callId;
    socket.join(`call:${data.callId}`);
    this.logger.log(`[WS] ${meta.managerId} joined call ${data.callId}`);

    return { status: 'joined', callId: data.callId };
  }

  @SubscribeMessage('call:transcript')
  async handleTranscriptChunk(
    @ConnectedSocket() socket: Socket,
    @MessageBody() data: RealtimeSuggestionDto,
  ) {
    const meta = this.connections.get(socket.id);
    if (!meta) return;

    try {
      const tip: RealtimeSuggestion = await this.negotiations.getRealtimeSuggestion(
        meta.orgId,
        meta.managerId,
        data,
      );

      // Send tip back to the manager (and all observers in same call room)
      const room = data.callId ? `call:${data.callId}` : socket.id;
      this.server.to(room).emit('coaching:tip', {
        callId: data.callId,
        tip,
        ts: Date.now(),
      });

      // Escalate urgent flags immediately
      if (tip.urgency === 'high') {
        this.server.to(room).emit('coaching:alert', {
          callId: data.callId,
          message: tip.tip,
          suggestedPhrase: tip.suggestedPhrase,
          ts: Date.now(),
        });
      }
    } catch (e: any) {
      this.logger.error(`[WS] Coaching error: ${e.message}`);
    }
  }

  @SubscribeMessage('call:end')
  handleCallEnd(
    @ConnectedSocket() socket: Socket,
    @MessageBody() data: { callId: string },
  ) {
    const meta = this.connections.get(socket.id);
    if (meta?.callId) {
      this.leaveCallRoom(socket.id, meta.callId);
      meta.callId = undefined;
    }
    this.logger.log(`[WS] Call ended: ${data.callId}`);
    return { status: 'left' };
  }

  // ─────────────────────── Server-initiated events ─────────────────────────

  /**
   * Called by ScoringWorker (via REST or internal event) when scorecard is ready.
   * Pushes final scorecard to all managers watching that call.
   */
  notifyScorecard(callId: string, scorecard: any) {
    this.server.to(`call:${callId}`).emit('coaching:scorecard', {
      callId,
      scorecard,
      ts: Date.now(),
    });
    this.logger.log(`[WS] Scorecard pushed for call ${callId}`);
  }

  /**
   * Notify a call room about status change (TRANSCRIBING → SCORING → DONE).
   */
  notifyCallStatus(callId: string, status: string) {
    this.server.to(`call:${callId}`).emit('call:status', { callId, status, ts: Date.now() });
  }

  // ─────────────────────── Helpers ─────────────────────────────────────────

  private leaveCallRoom(socketId: string, callId: string) {
    const room = this.callRooms.get(callId);
    if (room) {
      room.delete(socketId);
      if (room.size === 0) this.callRooms.delete(callId);
    }
  }
}
