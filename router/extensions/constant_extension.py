import re

from markdown import Markdown
from markdown.extensions import Extension
from markdown.postprocessors import Postprocessor


class ConstExtension(Extension):
    def __init__(self, **kwargs):
        self.config = {
            "constants": [{}, "Dictionary of constants"],
        }
        super().__init__(**kwargs)

    def extendMarkdown(self, md: Markdown):
        constants = self.getConfig("constants")
        md.postprocessors.register(
            ConstPostprocessor(constants), "const_postprocessor", 10
        )


class ConstPostprocessor(Postprocessor):
    def __init__(self, constants):
        self.constants = constants

    def run(self, text):
        def replace_const(m):
            key = m.group(1).strip()
            return self.constants.get(
                key, f'<span class="missing">missing constant: {key}</span>'
            )

        pattern = re.compile(r"(?<!\\)!constant\[(.+?)\]")
        text = pattern.sub(replace_const, text)

        text = text.replace(r"\!constant", "!constant")
        return text
