"""All unit tests are offline. An unmocked provider call is a test failure."""
import socket
import os

import pytest


@pytest.fixture(autouse=True)
def reject_unmocked_network(monkeypatch, request):
    attempted = []

    def reject(*args, **kwargs):
        attempted.append(True)
        raise OSError("Outbound network is disabled in BXK tests; mock the provider.")

    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_getaddrinfo = socket.getaddrinfo
    local_pg = None
    if request.node.path.name == "test_setup_invitation_postgres.py" and os.environ.get("BXK_TEST_POSTGRES_URL"):
        # Only this integration module may resolve its already-validated
        # loopback PostgreSQL target. This does not permit provider/proxy DNS.
        try:
            url = request.module._safe_test_url(os.environ["BXK_TEST_POSTGRES_URL"])
            local_pg = (url.host, url.port or 5432)
        except ValueError:
            pass  # The integration fixture itself reports the unsafe target.

    def guarded_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        if local_pg and host == local_pg[0] and str(port) == str(local_pg[1]):
            address = "127.0.0.1" if host == "localhost" else host
            return original_getaddrinfo(address, port, family, type, proto, flags | socket.AI_NUMERICHOST)
        return reject()

    def guarded_connect(sock, address):
        if sock.family == socket.AF_UNIX:
            return original_connect(sock, address)
        return reject()

    def guarded_connect_ex(sock, address):
        if sock.family == socket.AF_UNIX:
            return original_connect_ex(sock, address)
        return reject()

    # TestClient/asyncio use local socket pairs, not Internet sockets. The
    # psycopg resolves its validated loopback address in Python, then uses
    # libpq transport. No HTTP/provider/proxy connection is permitted.
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
    monkeypatch.setattr(socket, "create_connection", reject)
    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    yield
    if attempted:
        pytest.fail(f"Unmocked network attempted by {request.node.nodeid}; the connection was blocked.")
