import ast
import sys
import textwrap

class Function:
  def __init__(self, name, program):
    self.program = program
    self.waitfor = 'main'
    self.name = name
    self.buffer = []
    self.arg_count = 0
  def next_window_index(self):
    return len(self.buffer)
  def write(self, contents, index=None):
    if contents is None:
      self.buffer.append(None)
    elif index is None:
      self.buffer.append(textwrap.dedent(contents))
    elif self.buffer[index] is not None:
      raise Exception("Invalid instruction overwrite")
    else:
      self.buffer[index] = textwrap.dedent(contents)
    return len(self.buffer) - 1
  def to_string(self):
    return '\n'.join(self.buffer)

  def new_window(self, body, index = None):
    index = index or self.next_window_index()
    target = self.name + ':{end}'
    colour = 16 + (index % (231 - 16))
    return textwrap.dedent("""\
      # index: %s
      new-window -a -t '%s' 'tmux wait-for %s'
      set -w -t '%s' window-style bg=colour%s
      set-hook -t '%s' pane-focus-in {\
    """ % (index, target, self.waitfor, target, colour, target) + body) + '}\n'

  def push_constant(self, value, index=None):
    self.write(self.new_window("""
        run "tmux set-buffer '%s'"
        run 'tmux next-window'
      """ % value, index), index)

  def pop_stack(self):
    self.write(self.new_window("""
        run "tmux delete-buffer"
        run 'tmux next-window'
      """))

  def store_top(self):
    index = self.next_window_index()
    self.write(self.new_window("""
        run 'tmux rename-window -t :=%s "#{buffer_sample}"'
        run 'tmux delete-buffer'
        run 'tmux next-window'
      """ % (index + 1), index))

  def maths_op(self, op):
    self.store_top()

    index = self.next_window_index()
    self.write(self.new_window("""
        run 'tmux rename-window -t :=%s "#{e|%s:#{buffer_sample},#{window_name}}"'
        run 'tmux delete-buffer'
        run 'tmux set-buffer "#{window_name}"'
        run 'tmux next-window'
      """ % (index, op), index))

  def print(self):
    self.write(self.new_window("""
        run 'tmux display -F "#{buffer_sample}"'
        run 'tmux delete-buffer'
        run 'tmux next-window'
      """))

  def print_str(self, text):
    self.write(self.new_window("""\
        run 'tmux display -F "%s"'
        run 'sleep 2'
        run 'tmux next-window'
      """ % text))

  def cond(self, invert=False):
    instruction_index = self.next_window_index()
    pos = self.write(None)
    def add_with_indexes_later():
      indexes = (instruction_index + 1, self.next_window_index())
      if invert:
        indexes = tuple(reversed(indexes))
      self.write(self.new_window("""
          run 'tmux select-window -t "#{?#{buffer_sample},:=%s,:=%s}"'
          run 'tmux delete-buffer'
        """ % indexes, pos), pos)
    return add_with_indexes_later

  def set_variable(self, name):
    self.write(self.new_window("""
        run 'tmux set-option -s '@%s' "#{buffer_sample}"'
        run 'tmux delete-buffer'
        run 'tmux next-window'
      """ % name))

  def get_variable(self, name):
    self.write(self.new_window("""
        run 'tmux set-buffer "#{@%s}"'
        run 'tmux next-window'
      """ % name))

  def switch_session(self, name):
    self.write(self.new_window("""
        run 'tmux switch-client -t %s:1'
      """ % name))

  def switch_back(self):
    self.write(self.new_window("""
        # the value to return
        run 'tmux rename-session -- "#{buffer_sample}"'
        run 'tmux delete-buffer'
        # the location to return to
        run 'tmux rename-window -- "#{buffer_sample}"'
        run 'tmux delete-buffer'
        # put return value back on stack
        run 'tmux set-buffer "#S"'
        # restore session name
        run 'tmux rename-session -- "%s"'
        run 'tmux switch-client -t "#{window_name}"'
      """ % self.name))

  def push_return(self):
    index = self.write(None)
    def cb():
      self.push_constant(self.name + ':' + str(self.next_window_index()), index)
    return cb

  def goto(self):
    index = self.write(None)
    def doit():
      self.write(self.new_window("""
          run 'tmux select-window -t :=%s'
        """ % self.next_window_index(), index), index)
    return doit

  def jump(self, index):
    self.write(self.new_window("""
        run 'tmux select-window -t :=%s'
      """ % index))

class Program:
  def __init__(self):
    self.functions = dict()
    func = self.main = self.add_func('main')
    func.write("""\
        # FUNCTION: %s
        new-session -d -s %s 'tmux wait-for %s'
        """ % (func.name, func.name, func.waitfor))

  def add_func(self, name):
    if name in self.functions:
      raise Exception("function already defined: " + name)
    func = Function(name, self)
    self.functions[func.name] = func
    return func

  def to_string(self):
    GLOBAL = textwrap.dedent('''
      set -g display-time 2000
      set -g focus-events on
    ''')
    FOOTER = '\nattach -t main'
    return GLOBAL + '\n'.join(f.to_string() for f in self.functions.values()) + FOOTER

def compile_if(self, func):
  self.test.compile_to(func)
  cb = func.cond()
  for expr in self.body:
    expr.compile_to(func)
    func.pop_stack()
  goto = func.goto()
  cb()
  for expr in self.orelse:
    expr.compile_to(func)
    func.pop_stack()
  goto()
  func.push_constant(0)
ast.If.compile_to = compile_if

def compile_boolop(self, func):
  if len(self.values) != 2:
    raise Exception("oh no boolop!")
  lhs = self.values[0]
  rhs = self.values[1]
  raise Exception("not implemented")
  # if type(self.op) is ast.And:
  #   # compile_and(func, lhs, rhs)
  # elif type(self.op) is ast.Or:
  #   # compile_or(func, lhs, rhs)
  # else:
  #   raise Exception("unknown op:", self)
ast.BoolOp.compile_to = compile_boolop

def compile_while(self, func):
  startindex = func.next_window_index()
  self.test.compile_to(func)
  cb = func.cond()
  for expr in self.body:
    expr.compile_to(func)
    func.pop_stack()
  func.jump(startindex)
  cb()
  func.push_constant(0)
ast.While.compile_to = compile_while

def compile_compare(self, func):
  self.left.compile_to(func)
  if len(self.comparators) != 1:
    raise Exception("only compare one thing!")
  self.comparators[0].compile_to(func)
  if len(self.ops) != 1:
    raise Exception("only compare one op!")
  self.ops[0].compile_to(func)
ast.Compare.compile_to = compile_compare

def compile_func(self, program):
  func = program.add_func(self.name)
  func.write("""\
      # FUNCTION: %s
      new-session -d -s %s 'tmux wait-for %s'
      """ % (func.name, func.name, func.waitfor))

  # args added to stack from first to last
  for arg in reversed(self.args.args):
    func.arg_count += 1
    func.set_variable(arg.arg)

  for expr in self.body:
    expr.compile_to(func)
    func.pop_stack()
  if type(self.body[-1]) is not ast.Return:
    func.push_constant(0)
    func.switch_back()
  func.write('select-window -t :=0')
ast.FunctionDef.compile_to = compile_func

def compile_return(self, func):
  self.value.compile_to(func)
  func.switch_back()
ast.Return.compile_to = compile_return

def compile_assign(self, func):
  if len(self.targets) != 1:
    raise Exception("only one assignment target pls")
  self.value.compile_to(func)
  name = self.targets[0].id
  func.set_variable(name)
  func.push_constant(0)
ast.Assign.compile_to = compile_assign

def compile_name(self, func):
  func.get_variable(self.id)
ast.Name.compile_to = compile_name

ast.Eq.compile_to = lambda self, func: func.maths_op('==')
ast.NotEq.compile_to = lambda self, func: func.maths_op('!=')
ast.Mod.compile_to = lambda self, func: func.maths_op('%')
ast.Lt.compile_to = lambda self, func: func.maths_op('<')
ast.Gt.compile_to = lambda self, func: func.maths_op('>')
ast.Add.compile_to = lambda self, func: func.maths_op('+')
ast.Sub.compile_to = lambda self, func: func.maths_op('-')
ast.Mult.compile_to = lambda self, func: func.maths_op('*')
ast.Div.compile_to = lambda self, func: func.maths_op('/')

def compile_const(self, func):
  func.push_constant(self.value)
ast.Constant.compile_to = compile_const

def compile_binop(self, func):
  self.left.compile_to(func)
  self.right.compile_to(func)
  self.op.compile_to(func)
ast.BinOp.compile_to = compile_binop

def compile_call(self, func):
  if self.func.id == 'print':
    if len(self.args) != 1:
      raise Exception("print only takes one argument")
    for arg in self.args:
      arg.compile_to(func)
    func.print()
    func.push_constant('0')
    return
  if self.func.id not in func.program.functions:
    raise Exception("unknown func: " + self.func.id)
  newfunc = func.program.functions[self.func.id]
  if newfunc.arg_count != len(self.args):
    raise Exception("Wrong number of args to call {} got {} expected {}".format(
      self.func.id, len(self.args), newfunc.arg_count))
  on_return = func.push_return()
  for arg in self.args:
    arg.compile_to(func)
  func.switch_session(self.func.id)
  on_return()
ast.Call.compile_to = compile_call

def compile_expr(self, func):
  self.value.compile_to(func)
ast.Expr.compile_to = compile_expr

def compile_module(self, program):
  for expr in self.body:
    if type(expr) is ast.FunctionDef:
      expr.compile_to(program)
    else:
      expr.compile_to(program.main)
      program.main.pop_stack()

  program.main.write('select-window -t :=0')

ast.Module.compile_to = compile_module


p = Program()


with open(sys.argv[1]) as f:
  tree = ast.parse(f.read())

print(ast.dump(tree, indent=2))

tree.compile_to(p)
print(p.to_string())

with open(sys.argv[2], 'wt') as o:
  o.write(p.to_string())

