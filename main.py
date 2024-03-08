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
  def write(self, contents):
    self.buffer.append(textwrap.dedent(contents))
  def to_string(self):
    return '\n'.join(self.buffer)

  def add_header(self):
    self.write("""\
        new-session -d -n %s 'read && tmux wait-for -S %s'
        set -g display-time 0
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
    index = self.next_window_index()
    self.write("""\
      new-window 'tmux wait-for %s'
      set-hook -t :=%s pane-focus-in {
        run 'tmux rename-window -t :=4 "#{e|%s:#{buffer_sample},#{window_name}}"'
        run 'tmux delete-buffer'
        run 'tmux set-buffer "#{window_name}"'
        run 'tmux next-window'
      }
      """ % (self.session, index, op))

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

  def ifeq(self):
    pass
   #new-window 'tmux wait-for test-session'
   #set-hook -t :=4 pane-focus-in {
   #  run 'tmux select-window -t "#{?#{e|==:#{buffer_sample},#{window_name}},:=5,:=6}"'
   #  run 'tmux delete-buffer'
   #}


p = Program()
p.add_header()
p.push_constant(1)
p.push_constant(2)
p.store_top()
p.maths_op('+')
p.print()
p.write('select-window -t :=0')

print(p.to_string())


with open(sys.argv[1]) as f:
  tree = ast.parse(f.read())

print(ast.dump(tree, indent=2))

with open(sys.argv[2], 'wt') as o:
  o.write(p.to_string())

