import ast
import sys
import textwrap

class Function:
  def __init__(self, name):
    self.waitfor = 'main'
    self.name = name
    self.index = 0
    self.buffer = []
  def next_window_index(self):
    self.index += 1
    return self.index
  def debug(self, text):
    self.buffer.append('\n# ' + text + '\n')
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

  def push_constant(self, value):
    index = self.next_window_index()
    self.write("""\
      new-window 'tmux wait-for %s'
      set-hook -t :=%s pane-focus-in {
        run "tmux set-buffer '%s'"
        run 'tmux next-window'
      }
      """ % (self.waitfor, index, value))

  def store_top(self, out_index=None):
    index = self.next_window_index()
    self.write("""\
      new-window 'tmux wait-for %s'
      set-hook -t :=%s pane-focus-in {
        run 'tmux rename-window -t :=%s "#{buffer_sample}"'
        run 'tmux delete-buffer'
        run 'tmux next-window'
      }
      """ % (self.waitfor, index, index + 1 if out_index is None else out_index))

  def maths_op(self, op):
    self.store_top()
    index = self.next_window_index()
    self.write("""\
      new-window 'tmux wait-for %s'
      set-hook -t :=%s pane-focus-in {
        run 'tmux rename-window -t :=%s "#{e|%s:#{buffer_sample},#{window_name}}"'
        run 'tmux delete-buffer'
        run 'tmux set-buffer "#{window_name}"'
        run 'tmux next-window'
      }
      """ % (self.waitfor, index, index, op))

  def print(self):
    index = self.next_window_index()
    self.write("""\
      new-window 'tmux wait-for %s'
      set-hook -t :=%s pane-focus-in {
        run 'tmux display -F "#{buffer_sample}"'
        run 'tmux delete-buffer'
        run 'tmux next-window'
      }
      """ % (self.waitfor, index))

  def print_str(self, text):
    index = self.next_window_index()
    self.write("""\
      new-window 'tmux wait-for %s'
      set-hook -t :=%s pane-focus-in {
        run 'tmux display -F "%s"'
        run 'sleep 2'
        run 'tmux next-window'
      }
      """ % (self.waitfor, index, text))

  def cond(self):
    instruction_index = self.next_window_index()
    pos = self.write(None)
    def add_with_indexes_later():
      self.write("""\
        new-window 'tmux wait-for %s'
        set-hook -t :=%s pane-focus-in {
          run 'tmux select-window -t "#{?#{buffer_sample},:=%s,:=%s}"'
          run 'tmux delete-buffer'
        }
        """ % (self.waitfor, instruction_index, instruction_index + 1, self.index + 1), pos)
    return add_with_indexes_later

  def set_variable(self, name):
    index = self.next_window_index()
    self.write("""\
      new-window 'tmux wait-for %s'
      set-hook -t :=%s pane-focus-in {
        run 'tmux set-option -s '@%s' "#{buffer_sample}"'
        run 'tmux delete-buffer'
        run 'tmux next-window'
      }
      """ % (self.waitfor, index, name))

  def get_variable(self, name):
    index = self.next_window_index()
    self.write("""\
      new-window 'tmux wait-for %s'
      set-hook -t :=%s pane-focus-in {
        run 'tmux set-buffer "#{@%s}"'
        run 'tmux next-window'
      }
      """ % (self.waitfor, index, name))


class Program:
  def __init__(self):
    self.buffer = []
    self.functions = dict()
    self.index = 0

  def add_func(self, *args):
    func = Function(*args)
    self.functions[func.name] = func
    return func

  def to_string(self):
    GLOBAL = textwrap.dedent('''
      set -g display-time 2000
      set -g focus-events on
    ''')
    return GLOBAL + '\n'.join(f.to_string() for f in self.functions.values())

def compile_func(self, program):
  func = program.add_func(self.name)
  func.debug("FUNCTION: " + func.name)
  func.write("""\
      new-session -d -n %s 'read && tmux wait-for -S %s'
      """ % (func.name, func.waitfor))

  # bind args from stack
  # run body
  for expr in self.body:
    expr.compile_to(func)
  # return
ast.FunctionDef.compile_to = compile_func

def compile_return(self, func):
  self.value.compile_to(func)
  func.write("return from %s" % func.name)
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
    raise Exception("only print is supported")
ast.Call.compile_to = compile_call

def compile_expr(self, func):
  self.value.compile_to(func)
ast.Expr.compile_to = compile_expr

def compile_module(self, program):
  for expr in self.body:
    if type(expr) is ast.FunctionDef:
      expr.compile_to(program)
    else:
      raise Exception("only functions at top level")

ast.Module.compile_to = compile_module


p = Program()


with open(sys.argv[1]) as f:
  tree = ast.parse(f.read())

print(ast.dump(tree, indent=2))

tree.compile_to(p)
print(p.to_string())

with open(sys.argv[2], 'wt') as o:
  o.write(p.to_string())

