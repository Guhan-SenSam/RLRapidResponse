import { useEffect, useState, useCallback, useRef } from 'react';
import { io } from 'socket.io-client';

const SOCKET_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

export function useWebSocket() {
  const [socket, setSocket] = useState(null);
  const [connected, setConnected] = useState(false);
  const eventHandlers = useRef(new Map());

  // Initialize socket connection
  useEffect(() => {
    const newSocket = io(SOCKET_URL, {
      transports: ['websocket'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: Infinity,
    });

    newSocket.on('connect', () => {
      console.log('WebSocket connected');
      setConnected(true);
    });

    newSocket.on('disconnect', () => {
      console.log('WebSocket disconnected');
      setConnected(false);
    });

    newSocket.on('connect_error', (error) => {
      console.error('WebSocket connection error:', error);
    });

    setSocket(newSocket);

    return () => {
      newSocket.close();
    };
  }, []);

  // Generic event listener
  const on = useCallback((eventName, handler) => {
    if (!socket) return null;

    // Store handler reference
    eventHandlers.current.set(eventName, handler);

    socket.on(eventName, handler);

    // Return cleanup function
    return () => {
      socket.off(eventName, handler);
      eventHandlers.current.delete(eventName);
    };
  }, [socket]);

  // Remove listener
  const off = useCallback((eventName) => {
    if (!socket) return;

    const handler = eventHandlers.current.get(eventName);
    if (handler) {
      socket.off(eventName, handler);
      eventHandlers.current.delete(eventName);
    }
  }, [socket]);

  // Emit event
  const emit = useCallback((eventName, data) => {
    if (!socket || !connected) {
      console.warn('Cannot emit event - socket not connected');
      return;
    }
    socket.emit(eventName, data);
  }, [socket, connected]);

  return {
    socket,
    connected,
    on,
    off,
    emit,
  };
}
