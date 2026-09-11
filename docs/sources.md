# Sources and scope

## Project evidence

- This conversation's operator-provided PI30 frames, D-Bus readings, supervisor/log output and screenshots.
- Earlier Word summary: `archive/inverter6200_cerbo_documentation-2026-09-10.docx` (retained unchanged).
- Latest owner report: the USB adapter was replaced and monitoring works immediately.
- The source on the actual Cerbo was NOT fetched during packaging. The main Python file is a reconstruction.

No full chat, screenshot set or private logs are bundled for public publication. The curated handover
separates confirmed observations from failed tests and unresolved hypotheses.

## Official external documentation checked during packaging (2026-09-11)

- Victron: rootfs/data persistence, hooks and service overlay:
  https://www.victronenergy.com/live/ccgx:root_access
- Victron VeDbusService implementation (external dependency, not vendored):
  https://github.com/victronenergy/velib_python/blob/master/vedbus.py
- GitHub: creating a repository:
  https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository
- OpenAI: GitHub account/repository authorization (surface capabilities can vary):
  https://help.openai.com/en/articles/11145903
- OpenAI: desktop Chat/Work/Codex and chat synchronization:
  https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex
- OpenAI: Codex access and clients:
  https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan
- OpenAI: Projects and moving an existing chat:
  https://help.openai.com/en/articles/10169521-projects-in-chatgpt
- OpenAI: official ChatGPT data export:
  https://help.openai.com/en/articles/7260999-how-do-i-export-my-chatgpt-history-and-data
- OpenAI: exported conversations are reference, not full account migration:
  https://help.openai.com/en/articles/9106926

These web references describe platforms. They do not establish compatibility of an untested driver
with this live battery/inverter installation. Verify the installed source/version before a deployment.
