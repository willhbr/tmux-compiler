import ast
import sys
import textwrap

class Program:
  def __init__(self):
    self.session = 'test-session'
    self.buffer = []
    self.index = 0

  def next_window_index(self):
    self.index += 1
    return self.index
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

  def add_header(self):
    self.write("""\
        new-session -d -n %s 'read && tmux wait-for -S %s'
        set -g display-time 2000
        set -g focus-events on
        """ % (self.session, self.session))

  def push_constant(self, value):
    index = self.next_window_index()
    self.write("""\
      new-window 'tmux wait-for %s'
      set-hook -t :=%s pane-focus-in {
        run "tmux set-buffer '%s'"
        run 'tmux next-window'
      }
      """ % (self.session, index, value))

  def store_top(self, out_index=None):
    index = self.next_window_index()
    self.write("""\
      new-window 'tmux wait-for %s'
      set-hook -t :=%s pane-focus-in {
        run 'tmux rename-window -t :=%s "#{buffer_sample}"'
        run 'tmux delete-buffer'
        run 'tmux next-window'
      }
      """ % (self.session, index, index + 1 if out_index is None else out_index))

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
      """ % (self.session, index, index, op))

  def print(self):
    index = self.next_window_index()
    self.write("""\
      new-window 'tmux wait-for %s'
      set-hook -t :=%s pane-focus-in {
        run 'tmux display -F "#{buffer_sample}"'
        run 'tmux delete-buffer'
        run 'tmux next-window'
      }
      """ % (self.session, index))

  def print_str(self, text):
    index = self.next_window_index()
    self.write("""\
      new-window 'tmux wait-for %s'
      set-hook -t :=%s pane-focus-in {
        run 'tmux display -F "%s"'
        run 'sleep 2'
        run 'tmux next-window'
      }
      """ % (self.session, index, text))

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
        """ % (self.session, instruction_index, instruction_index + 1, self.index + 1), pos)
    return add_with_indexes_later

ast.Add.compile_to = lambda self, program: program.maths_op('+')
ast.Sub.compile_to = lambda self, program: program.maths_op('-')
ast.Mult.compile_to = lambda self, program: program.maths_op('*')
ast.Div.compile_to = lambda self, program: program.maths_op('/')

def compile_const(self, program):
  program.push_constant(self.value)
ast.Constant.compile_to = compile_const

def compile_binop(self, program):
  self.left.compile_to(program)
  self.right.compile_to(program)
  self.op.compile_to(program)
ast.BinOp.compile_to = compile_binop

def compile_call(self, program):
  for arg in self.args:
    arg.compile_to(program)
  if self.func.id == 'print':
    p.print()
  else:
    raise Exception("only print is supported")
ast.Call.compile_to = compile_call

def compile_expr(self, program):
  self.value.compile_to(program)
ast.Expr.compile_to = compile_expr

def compile_module(self, program):
  program.add_header()
  for expr in self.body:
    expr.compile_to(program)
  p.write('select-window -t :=0')

ast.Module.compile_to = compile_module


p = Program()
# p.push_constant(1)
# cb = p.cond()
# p.print_str("Hello world")
# # p.print_str("second print")
# p.write('new-window')
# cb()
# p.write('select-window -t :=0')
# 
# print(p.to_string())


with open(sys.argv[1]) as f:
  tree = ast.parse(f.read())

print(ast.dump(tree, indent=2))

tree.compile_to(p)
print(p.to_string())

with open(sys.argv[2], 'wt') as o:
  o.write(p.to_string())

