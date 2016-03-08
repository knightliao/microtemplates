#!/usr/bin/env python
# coding=utf8
import ast
import operator

from pytemplate.core import operator_lookup_table, WHITESPACE
from pytemplate.core.error import TemplateContextError, TemplateSyntaxError, TemplateError


class _Node(object):
    creates_scope = False

    def __init__(self, fragment=None):
        self.children = []
        self.process_fragment(fragment)

    def process_fragment(self, fragment):
        pass

    def enter_scope(self):
        pass

    def render(self, context):
        pass

    def exit_scope(self):
        pass

    def render_children(self, context, children=None):
        if children is None:
            children = self.children

        # render every children node and join
        def render_child(child):
            child_html = child.render(context)
            return '' if not child_html else str(child_html)

        return ''.join(map(render_child, children))


class _Root(_Node):
    def render(self, context):
        return self.render_children(context)


class _Text(_Node):
    def process_fragment(self, fragment):
        self.text = fragment

    def render(self, context):
        return self.text


def resolve(name, context):
    if name.startswith('..'):
        context = context.get('..', {})
        name = name[2:]
    try:

        # get variable's properties
        for tok in name.split('.'):
            context = context[tok]
        return context

    except KeyError:
        raise TemplateContextError(name)


class _Variable(_Node):
    def process_fragment(self, fragment):
        self.name = fragment

    def render(self, context):
        return resolve(self.name, context)


class _ScopableNode(_Node):
    creates_scope = True


def eval_expression(expr):
    try:
        return 'literal', ast.literal_eval(expr)
    except ValueError, SyntaxError:
        return 'name', expr


class _If(_ScopableNode):
    def process_fragment(self, fragment):

        bits = fragment.split()[1:]

        if len(bits) not in (1, 3):
            raise TemplateSyntaxError(fragment)

        # get left value
        self.lhs = eval_expression(bits[0])

        # if three ops, get op and right value
        if len(bits) == 3:
            self.op = bits[1]
            self.rhs = eval_expression(bits[2])

    def render(self, context):

        # get left value
        lhs = self.resolve_side(self.lhs, context)

        # three ops
        if hasattr(self, 'op'):
            op = operator_lookup_table.get(self.op)
            if op is None:
                raise TemplateSyntaxError(self.op)

            # get right value
            rhs = self.resolve_side(self.rhs, context)

            # make op
            exec_if_branch = op(lhs, rhs)

        else:

            # one op
            exec_if_branch = operator.truth(lhs)

        if_branch, else_branch = self.split_children()
        return self.render_children(context,
                                    self.if_branch if exec_if_branch else self.else_branch)

    # if constants , return ; if variable, resolve
    def resolve_side(self, side, context):
        return side[1] if side[0] == 'literal' else resolve(side[1], context)

    def exit_scope(self):
        self.if_branch, self.else_branch = self.split_children()

    #
    # 递归式的获取左子树,一旦发现else,则递归的获取右子树
    #
    def split_children(self):
        if_branch, else_branch = [], []
        curr = if_branch
        for child in self.children:
            if isinstance(child, _Else):
                curr = else_branch
                continue
            curr.append(child)
        return if_branch, else_branch


class _Else(_Node):
    def render(self, context):
        pass


class _Each(_ScopableNode):
    def process_fragment(self, fragment):
        try:
            _, it = WHITESPACE.split(fragment, 1)
            self.it = eval_expression(it)
        except ValueError:
            raise TemplateSyntaxError(fragment)

    def render(self, context):

        # 进行解析
        items = self.it[1] if self.it[0] == 'literal' else resolve(self.it[1], context)

        def render_item(item):
            return self.render_children({'..': context, 'it': item})

        return ''.join(map(render_item, items))


class _Call(_Node):
    def process_fragment(self, fragment):
        try:
            bits = WHITESPACE.split(fragment)

            # get function & argus
            self.callable = bits[1]

            # 解析出 参数和kwargs
            self.args, self.kwargs = self._parse_params(bits[2:])

        except ValueError, IndexError:
            raise TemplateSyntaxError(fragment)

    def _parse_params(self, params):
        args, kwargs = [], {}
        for param in params:
            if '=' in param:
                name, value = param.split('=')
                kwargs[name] = eval_expression(value)
            else:
                args.append(eval_expression(param))
        return args, kwargs

    def render(self, context):
        resolved_args, resolved_kwargs = [], {}

        # 参数进行解析
        for kind, value in self.args:
            if kind == 'name':
                value = resolve(value, context)
            resolved_args.append(value)

        # 解析kwargs
        for key, (kind, value) in self.kwargs.iteritems():
            if kind == 'name':
                value = resolve(value, context)
            resolved_kwargs[key] = value

        # 解析调用函数
        resolved_callable = resolve(self.callable, context)
        if hasattr(resolved_callable, '__call__'):
            # 添加 kwargs
            return resolved_callable(*resolved_args, **resolved_kwargs)
        else:
            raise TemplateError("'%s' is not a callable" % self.callable)
