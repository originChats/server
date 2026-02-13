# Changes and additions made.

## Discord
The discord plugin got a major overhaul. Before it would break the json file for the channel you were in if you sent an emoji on either end. The emoji would not display, and would break the json string, making it unreadable and unable to accept new messages, thus needing a full reset of the file. This is now fixed, hopefully soon I will also add some other features to this to make the Discord <--> Originchats client nearly seamless.

## Logger
The logger.py file got a few more just "codes" I suppose to make it easier to program with.

## Exampleplugin.py
An example plugin meant to make programming plugins, which are essentially like discord bots if I had to compare them to something, that simply just says, "Hello World!" whenever any user types !helloworld.