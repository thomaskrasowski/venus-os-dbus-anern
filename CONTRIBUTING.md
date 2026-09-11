# Contributing

Read AGENTS.md and SOURCE-STATUS.md first. Start in a branch. Prefer small changes with offline tests.
Capture and compare the deployed file before claiming a release matches the live Cerbo.

Keep code-review and installation separate. An approved PR is not approval to change BMS settings or restart
core GX services. Include expected behavior, tested frames, failure behavior and rollback instructions.
Do not add a license or publish the project without the owner's choice.

Use LF for target shell/Python files. Run `python -m unittest discover -s tests -v`.
Test paths/types and invalid CRC/NAK handling, not just syntax. Hardware tests must be explicit and
must not compete with the running driver for the serial port.
