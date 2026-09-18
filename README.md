# penr-oz-jev-syslog-analyzer
An asyncio daemon that tails journald or syslog and asks Jev, for each event, which subsystem it belongs to, how severe it is, and whether it's noise. Plain code then ignores the event, alerts on it, or escalates it to a human when confidence is low.
