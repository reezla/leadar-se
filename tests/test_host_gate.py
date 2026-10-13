import threading

from lead_finder.providers.rate_limit import HostRequestGate


def test_same_host_waits_for_the_gap_and_other_hosts_do_not() -> None:
    now = 0.0
    delays: list[float] = []

    def clock() -> float:
        return now

    def sleep(delay: float) -> None:
        nonlocal now
        delays.append(delay)
        now += delay

    gate = HostRequestGate(
        max_in_flight=4,
        per_host_in_flight=3,
        host_gap_seconds=1,
        clock=clock,
        sleep=sleep,
    )
    gate.acquire("a.se")
    gate.acquire("b.se")
    gate.acquire("a.se")
    assert delays == [1]
    gate.release("a.se")
    gate.release("a.se")
    gate.release("b.se")


def test_global_cap_blocks_until_a_slot_is_free() -> None:
    gate = HostRequestGate(max_in_flight=1, per_host_in_flight=1, host_gap_seconds=0)
    gate.acquire("a.se")
    started = threading.Event()
    finished = threading.Event()

    def other() -> None:
        started.set()
        gate.acquire("b.se")
        finished.set()
        gate.release("b.se")

    thread = threading.Thread(target=other)
    thread.start()
    assert started.wait(1)
    assert finished.wait(0.05) is False
    gate.release("a.se")
    assert finished.wait(1)
    thread.join(1)
