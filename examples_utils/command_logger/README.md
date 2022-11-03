## Command logger

All applications should call the log command as follows:

```
...
from examples_utils.command_logger.config_logger import ConfigLogger

...

if __name__ == "__main__":
    ConfigLogger.log_example_config_run()
    ...
```

The logging function would be configured to be executed on cloud servers by setting the `GC_EXAMPLE_LOG_TARGET` environment variable to `LOCAL` (note: this could allow for other configurations of the tool to log to different targets, for instance maybe a web API). If the `GC_EXAMPLE_LOG_TARGET` environment variable is not set, then the tool will do nothing.

If the tool is configured to run, then it will look for a configuration file at `~/.graphcore/config.json` which will contain a variable `GC_EXAMPLE_LOG_STATE` either `ENABLED` or `DISABLED`. If it is disabled, again, the tool will exit and do nothing.

If no config file exists at `~/.graphcore/config.json` then the user will be prompted to answer whether they want to enable or disable the tool with the following message.

```
"Graphcore would like to collect information about which examples and configurations have been run to improve usability and support for future users.\n\n"
"The information will be anonymised and logged locally to a file in `~/.graphcore` to be collected by your cloud provider.\n\n"
"You can update this permission in future by setting the GC_EXAMPLE_LOG_STATE to ENABLE or DISABLE in a config file at `~/.graphcore/command_logging_config.json`.\n\n"
```

This choice will be saved and used for all future usage of public examples and tutorials.

If the tool is enabled, it will log the following information to a daily, dated json file at `~/.graphcore/logs/f"{time.strftime('%Y_%m_%d')}.json"`. It is split into daily logs to cap the size of the log files and simplify collection of logs by the cloud provider or graphcore.

Information captured:
- unix timestamp
- truncated hash of concatenated username and mac address of the machine (mac address used to obfuscate the user name hash which might otherwise be too easy to derive)
- script name
- repository name
- example path (from root of repo)
- command arguments

This is meant as a prototype to demonstrate how the capability could be implemented.
