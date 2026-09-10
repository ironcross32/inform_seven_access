# Inform 7 Accessibility Enhancements

### Premise

[Inform](https://ganelson.github.io/inform-website/) Is a big name in the Interactive  Fiction space. It empowers anyone to create their own games using natural language. It comes with an IDE with in-built documentation, testing tools, and reference material.

Inform even comes with a set of keyboard shortcuts which allow jumping to various parts of the interface. One thing it lacks; however, is accessibility support for those who use [screen readers](https://afb.org/blindness-and-low-vision/using-technology/assistive-technology-products/screen-readers). This includes blind and visually impaired developers, and could include people with print disabilities as well. Among the various choices on Windows, [nvda](https://www.nvaccess.org/) stands out for two reasons. It's free of charge, and it's open source.

Where NVDA doesn't work well with a particular app, chances are, there's an addon made by its community of users. Of course, there are addons for all sorts of things, and not all of them resolve a particular issue. Some of them add extra functionality to NVDA. This addon sets out to do a bit of both.

### Usage

After installation, focus the Inform application. As you arrow through your source text, you'll get announcements for quoted text, text substitutions. comments, and headings. If you wish, you can locate the Inform 7 category in NVDA's settings and enable sounds for these announcements, or turn them off entirely.

Upon successfully translating the game, either by clicking the **Go** button in the actions toolbar or by pressing F5, you'll land in the interpreter area. As you execute commands, their output will be read automatically. You may also review the output using these keystrokes, which all include holding **CTRL** and **SHIFT** along with tapping the folllowing keys:
- **U**: Move to the previous line and speak it
- **I**: Read the current line
- **O**: Move to the next line and speak it
- **N**: Jump to the last line and speak it
- **Y**: Jump to the first line and speak it

The advantage of reviewing the output this way rather than using the review cursor is that this cursor won't be disturbed by typing or other announcements, and will hold your place for you when new text arrives.

There is one additional keystroke that applies while the interpreter window has focus, and it's a standard NVDA keystroke that reads the wrong thing in Inform, so this addon overrides its functionality. Whenever you read the status bar, either **NVDA+END** on the *desktop* layout or **NVDA+SHIFT+END** on the *laptop* layout, it'll instead read the game's status line.

### Building

First, follow [these instructions](https://github.com/nvdaaddons/DevGuide/wiki/NVDA-Add-on-Development-Guide#setting-up-your-add-on-development-environment) to get your developer environment setup, then clone the repository, change into it's directory, preferably with a virtual environment activated and build. The process might look like this:
```
git clone https://github.com/ironcross32/inform_seven_accessibility.git
cd inform_seven_accessibility
scons -s
```
If all goes well, an NVDA addon will be produced. Pressing **ENTER** on it will start the installation process.
