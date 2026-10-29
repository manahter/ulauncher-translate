# Utilized resources
# https://github.com/YogurtTheHorse/ulauncher-translator
# https://github.com/mouuff/mtranslate
from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import KeywordQueryEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.HideWindowAction import HideWindowAction
from ulauncher.api.shared.action.CopyToClipboardAction import CopyToClipboardAction
import json
import socket
import textwrap
import urllib.error
import urllib.parse
import urllib.request

# The old endpoint (translate.google.com/m, HTML scraping) now answers
# 429 Too Many Requests / redirects to google.com/sorry for many IPs, which
# left the extension stuck on "loading". This endpoint returns JSON.
BASE_URL = "https://clients5.google.com/translate_a/t"
AGENT = {'User-Agent': "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"}
TIMEOUT = 10


class TranslateError(Exception):
    pass


def translate(to_translate, to_language="auto", from_language="auto", wrap_len="80"):
    params = urllib.parse.urlencode({
        "client": "dict-chrome-ex",
        "sl": from_language,
        "tl": to_language,
        "q": to_translate,
    })
    request = urllib.request.Request("%s?%s" % (BASE_URL, params), headers=AGENT)
    try:
        raw_data = urllib.request.urlopen(request, timeout=TIMEOUT).read()
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise TranslateError("Google is rate limiting this IP (HTTP 429). Try again later.")
        raise TranslateError("Google returned HTTP %s" % e.code)
    except (urllib.error.URLError, socket.timeout) as e:
        raise TranslateError("Network error: %s" % getattr(e, "reason", e))

    try:
        data = json.loads(raw_data.decode("utf-8"))
        # sl=auto -> [["translation", "detected-lang"]]
        # sl=xx   -> ["translation"]
        first = data[0]
        result = first[0] if isinstance(first, list) else first
    except (ValueError, IndexError, TypeError):
        raise TranslateError("Unexpected response from Google")

    width = int(wrap_len) if str(wrap_len).isdigit() else 80
    return "\n".join(
        "\n".join(textwrap.wrap(line, width)) for line in result.splitlines()
    )


class TranslateExtension(Extension):
    def __init__(self):
        super(TranslateExtension, self).__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())


class KeywordQueryEventListener(EventListener):
    def on_event(self, event, extension):
        query = event.get_argument() or str()
        
        if len(query.strip()) == 0:
            return RenderResultListAction([
                ExtensionResultItem(icon='images/icon.png',
                                    name='No input',
                                    on_enter=HideWindowAction())
            ])
        
        if len(query)>3 and ":" in query[0]:
            from_language = "auto"
            to_language = query[1:3]
            query = query[3:]
        elif len(query)>5 and ":" in query[2]:
            from_language = query[:2]
            to_language = query[3:5]
            query = query[5:]
        else:
            from_language = extension.preferences["otherlang"]
            to_language = extension.preferences["mainlang"]

        try:
            ceviri = translate(query, to_language, from_language, extension.preferences["wrap"])
        except TranslateError as e:
            return RenderResultListAction([
                ExtensionResultItem(icon='images/icon.png',
                                    name="Translation failed",
                                    description=str(e),
                                    on_enter=HideWindowAction())
            ])

        items = [
            ExtensionResultItem(icon='images/icon.png',
                                name=query.replace("\n",""),
                                description=ceviri,
                                on_enter=CopyToClipboardAction(ceviri))
        ]

        return RenderResultListAction(items)


if __name__ == '__main__':
    TranslateExtension().run()
