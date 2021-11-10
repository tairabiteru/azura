# Change log

### Azura 3.0 R.86 'Sapphirine Songstress'
- Fixed an issue with Youtube search in the `-play` command.
- Split Azura into two to allow multiple bots in the same server.
- Moved `wavelink.Client` to `bot` to allow it to be accessed outside of `Music` cog.
- Azura now disconnects when she is reinitialized.
  - She will send an apology message to the `plyrmsg` channel, if available. Otherwise, she just does so without warning.
- Added the `-dequeue` command.
  - This command allows members to remove songs from the queue based upon either a member specified in the command's arguments, or when nothing is passed, by who still remains in the voice channel the bot is connected to.
- Overhauled the logging methodology. Azura now logs to files as well as the console.
- Added the `-lint` command to perform code linting.
- Azura now gives more descriptive failure messages when enqueueing.
- Fixed a bug which allowed trailing whitespaces in generator strings.
