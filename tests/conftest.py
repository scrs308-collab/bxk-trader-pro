"""All unit tests are offline. An unmocked provider call is a test failure."""
import socket

import pytest


@pytest.fixture(autouse=True)
def reject_unmocked_network(monkeypatch, request):
    attempted = []

    def reject(*args, **kwargs):
        attempted.append(True)
        raise OSError("Outbound network is disabled in BXK tests; mock the provider.")

    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def guarded_connect(sock, address):
        if sock.family == socket.AF_UNIX:
            return original_connect(sock, address)
        return reject()

    def guarded_connect_ex(sock, address):
        if sock.family == socket.AF_UNIX:
            return original_connect_ex(sock, address)
        return reject()

    # TestClient/asyncio use local socket pairs, not Internet sockets. The
    # PostgreSQL-only suite validates its isolated localhost database URL and
    # uses psycopg's libpq transport; no HTTP provider access is permitted.
    monkeypatch.setattr(socket, "getaddrinfo", reject)
    monkeypatch.setattr(socket, "create_connection", reject)
    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    yield
    if attempted:
        pytest.fail(f"Unmocked network attempted by {request.node.nodeid}; the connection was blocked.")
