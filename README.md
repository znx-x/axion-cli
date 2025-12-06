# Axion CLI

An AI CLI terminal - similar to Gemini's CLI - compatible with OpenAI-style APIs (supports Open WebUI API as well).

It can natively access the web to perfrom web searches and fetch/scrape URLs.

## Installation

Clone the repository to your machine using `git clone`:

```bash
git clone https://github.com/znx-x/axion-cli
```

Navigate into the cloned repository:

```bash
cd axion-cli
```

Install all the dependencies using `pip`:

```bash
pip install -r requirements.txt
```

* You will need to use `venv` and set up a Virtual Environment if you're using macOS or Linux.

## Configuration

Rename the `config.ini.EXAMPLE` to `config.ini`:

```bash
mv config.ini.EXAMPLE config.ini
```

Edit the configuration file to add your API endpoint and key. It supports any API using OpenAI's standard endpoints, including Ollama and Open WebUI.

```bash
nano config.ini
```

### Tool Calling

Axion has *Web Search*, *URL Scraping*, and *Time Awareness* tools built-in. There's no API-keys or any configuration required for these tools to function, but you need to make sure that you set the `tool_mode` to reflect your model's tool calling framework - either `native` or `manual` (for models that do not support OpenAI tool calling).

You can *enable* or *disable* access to these tools via the `config.ini` file.

## Running

You can run the application with Python:

```bash
python axion.py
```

To load an existing conversation, you can use the `--load` flag:

```bash
python axion.py --load XYZ
```

All conversations are saved inside the `conversations` folder in a `.json` format.

## Compiling

You can compile the code into an executable/binary file with `pyinstaller`:

```bash
pyinstaller --noconfirm --onefile --console --name "Axion" --clean axion.py
```

If you prefer to use the `Axion.spec` file to set up your compiler settings, run:

```bash
pyinstaller Axion.spec
```
