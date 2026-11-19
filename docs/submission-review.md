# INT6181 Group 10 — Source submission review

The submission combines the upstream Cloudflare/OOP baseline `9779ee7`, member 3's input validation and error handling `c129329`, and member 4's tests, docstrings and Core CI `6767253`. Member 2's refactor is already in the upstream baseline. Member 4's branch contains member 3's commit.

- [Member 2 — OOP and modularization](https://github.com/Sukiyin516/Planwise/tree/oop-modularization)
- [Member 3 — input validation and error handling](https://github.com/Z3ych1k/Planwise/pull/1)
- [Member 4 — boundary tests, documentation and CI](https://github.com/syzzZ816/Planwise/tree/feature/tests-ci)

## Integration review

The event expansion in `6767253` omitted the unsplit event fields expected by the local Android calendar. It also missed one-off moves from original dates outside the queried range. The submission restores the original fields and includes override origin dates when expanding events. Two regression tests in `test_events.py` reproduce the original failures and verify rendering and protected time after a move.

`main.py` launches the existing NAS web application for assessment on a local computer, with a separate SQLite file and loopback access. See the root README for setup.

## How to reproduce

Run `python -m unittest discover -v` and `node --test nas/test_client.cjs` from the extracted folder. The existing NAS workflow also defines Docker build and container checks. The fork's Core CI result applies to the fork commit; this ZIP includes the additional submission changes described above. The prior contribution notes and logs in this repository record their original development snapshots.

## First-run account update

A fresh local database previously displayed the NAS invitation form before anyone could create an invitation. The coursework launcher now enables one-time first account creation through the browser. Registration still needs an invitation when using a NAS deployment. The first-run tests cover the launcher, the initial account, concurrent setup attempts, and behavior on both local and NAS configurations.
