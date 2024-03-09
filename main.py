import ast
import sys
import textwrap

class Function:
  def __init__(self, name, program):
    self.program = program
    self.waitfor = 'main'
    self.name = name
    self.index = 0
    self.buffer = []
  def next_window_index(self):
    self.index += 1
    return self.index
  def debug(self, text):
    self.buffer.append('\n# ' + text)
  def write(self, contents, index=None):
    self.debug('Instruction num: ' + str(index or self.index))
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
    return textwrap.dedent("""\
      new-window -a -t '%s' 'tmux wait-for %s'
      set-hook -t '%s' pane-focus-in {\
    """ % (target, self.waitfor, target) + body) + '}\n'

  def push_constant(self, value):
    self.write(self.new_window("""
        run "tmux set-buffer '%s'"
        run 'tmux next-window'
      """ % value))

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

  def cond(self):
    instruction_index = self.next_window_index()
    pos = self.write(None)
    def add_with_indexes_later():
      self.write(self.new_window("""
          run 'tmux select-window -t "#{?#{buffer_sample},:=%s,:=%s}"'
          run 'tmux delete-buffer'
        """ % (instruction_index + 1, self.index)), pos)
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
        run 'tmux switch-client -t %s'
      """ % name))

  def goto(self):
    index = self.write(None)
    def doit():
      self.write(self.new_window("""
          run 'tmux select-window -t :=%s'
        """ % self.index), index)
    return doit

  def jump(self, index):
    self.write(self.new_window("""
        run 'tmux select-window -t :=%s'
      """ % index))

class Program:
  def __init__(self):
    self.functions = dict()
    func = self.main = self.add_func('main')
    func.debug("FUNCTION: " + func.name)
    func.write("""\
        new-session -d -s %s 'read && tmux wait-for -S %s'
        """ % (func.name, func.waitfor))

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
  func.debug("if condition")
  self.test.compile_to(func)
  cb = func.cond()
  for expr in self.body:
    expr.compile_to(func)
  goto = func.goto()
  cb()
  for expr in self.orelse:
    expr.compile_to(func)
  goto()
ast.If.compile_to = compile_if

def compile_while(self, func):
  startindex = func.index + 1
  func.debug("while condition:")
  self.test.compile_to(func)
  cb = func.cond()
  func.debug("while body:")
  for expr in self.body:
    expr.compile_to(func)
  func.jump(startindex)
  func.debug("while end")
  cb()
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
  func.debug("FUNCTION: " + func.name)
  func.write("""\
      new-session -d -s %s 'read && tmux wait-for -S %s'
      """ % (func.name, func.waitfor))

  # args added to stack from first to last
  for arg in reversed(self.args.args):
    func.debug("SET arg %s IN %s" % (arg.arg, func.name))
    func.set_variable(arg.arg)

  for expr in self.body:
    expr.compile_to(func)
  if type(self.body[-1]) is not ast.Return:
    do_return(func)
  func.write('select-window -t :=0')
ast.FunctionDef.compile_to = compile_func

def do_return(func):
  func.debug("RETURN from %s" % func.name)

def compile_return(self, func):
  self.value.compile_to(func)
  do_return(func)
ast.Return.compile_to = compile_return

def compile_assign(self, func):
  if len(self.targets) != 1:
    raise Exception("only one assignment target pls")
  self.value.compile_to(func)
  name = self.targets[0].id
  func.set_variable(name)
ast.Assign.compile_to = compile_assign

def compile_name(self, func):
  func.get_variable(self.id)
ast.Name.compile_to = compile_name

ast.Eq.compile_to = lambda self, func: func.maths_op('==')
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
  for arg in self.args:
    arg.compile_to(func)
  if self.func.id == 'print':
    func.print()
  else:
    if self.func.id in func.program.functions:
      func.switch_session(self.func.id)
    else:
      raise Exception("unknown func: " + self.func.id)
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

ast.Module.compile_to = compile_module


p = Program()


with open(sys.argv[1]) as f:
  tree = ast.parse(f.read())

print(ast.dump(tree, indent=2))

tree.compile_to(p)
print(p.to_string())

with open(sys.argv[2], 'wt') as o:
  o.write(p.to_string())

