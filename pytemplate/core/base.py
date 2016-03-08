#!/usr/bin/env python
# coding=utf8
from pytemplate.core import TOK_REGEX, VAR_TOKEN_START, BLOCK_TOKEN_START, VAR_FRAGMENT, CLOSE_BLOCK_FRAGMENT, \
    OPEN_BLOCK_FRAGMENT, TEXT_FRAGMENT
from pytemplate.core.error import TemplateError, TemplateSyntaxError
from pytemplate.core.node import _Root, _Variable, _Text, _Each, _If, _Else, _Call


class _Fragment(object):
    def __init__(self, raw_text):
        self.raw = raw_text
        self.clean = self.clean_fragment()

    def clean_fragment(self):
        if self.raw[:2] in (VAR_TOKEN_START, BLOCK_TOKEN_START):
            return self.raw.strip()[2:-2].strip()
        return self.raw

    # judge the type :
    # var/block(open/close)/text
    @property
    def type(self):
        raw_start = self.raw[:2]
        if raw_start == VAR_TOKEN_START:
            return VAR_FRAGMENT
        elif raw_start == BLOCK_TOKEN_START:
            return CLOSE_BLOCK_FRAGMENT if self.clean[:3] == 'end' else OPEN_BLOCK_FRAGMENT
        else:
            return TEXT_FRAGMENT


class Compiler(object):
    def __init__(self, template_string):
        self.template_string = template_string

    def each_fragment(self):
        for fragment in TOK_REGEX.split(self.template_string):
            if fragment:
                yield _Fragment(fragment)

    def compile(self):

        root = _Root()
        scope_stack = [root]

        # parse total tree
        for fragment in self.each_fragment():

            if not scope_stack:
                raise TemplateError('nesting issues')

            # get parent
            parent_scope = scope_stack[-1]

            if fragment.type == CLOSE_BLOCK_FRAGMENT:
                parent_scope.exit_scope()
                scope_stack.pop()
                continue

            # create node
            new_node = self.create_node(fragment)
            if new_node:
                # add children for the parent
                parent_scope.children.append(new_node)
                if new_node.creates_scope:
                    scope_stack.append(new_node)
                    new_node.enter_scope()
        return root

    def create_node(self, fragment):
        node_class = None

        if fragment.type == TEXT_FRAGMENT:
            node_class = _Text

        elif fragment.type == VAR_FRAGMENT:
            node_class = _Variable

        elif fragment.type == OPEN_BLOCK_FRAGMENT:
            cmd = fragment.clean.split()[0]
            if cmd == 'each':
                node_class = _Each
            elif cmd == 'if':
                node_class = _If
            elif cmd == 'else':
                node_class = _Else
            elif cmd == 'call':
                node_class = _Call

        if node_class is None:
            raise TemplateSyntaxError(fragment)

        return node_class(fragment.clean)


class Template(object):
    def __init__(self, contents):
        self.contents = contents
        self.root = Compiler(contents).compile()

    def render(self, **kwargs):
        return self.root.render(kwargs)
