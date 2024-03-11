import textwrap
import sys

class Program:
  def __init__(self):
    self.buffer = []
    self.index = 0
    self.waitfor = 'main'
    self.append("new-session -d 'read && tmux wait-for -S %s'" % self.waitfor)
    self.append("set -s focus-events on")
    self.append('set -s @input "$INPUT"')
  def next_window_index(self):
    self.index += 1
    return self.index
  def to_string(self):
    return '\n'.join(self.buffer)
  def new_window(self, body, index = None):
    index = index or self.next_window_index()
    target = ':{end}'
    colour = 16 + (index % (231 - 16))
    return textwrap.dedent("""\
      # instruction number %s
      new-window -a -t '%s' 'tmux wait-for %s'
      set -w -t '%s' window-style bg=colour%s
      set-hook -t '%s' pane-focus-in {\
    """ % (index, target, self.waitfor, target, colour, target) + body) + '}\n'
  def append(self, text):
    self.buffer.append(textwrap.dedent(text))

  def move_right(self):
    self.append(self.new_window("""
        run 'tmux rename-session -- "#{e|+:#S,1}"'
        run 'tmux next-window'
        """))
  def move_left(self):
    self.append(self.new_window("""
        run 'tmux rename-session -- "#{e|-:#S,1}"'
        run 'tmux next-window'
        """))

  def inc(self):
    self.append(self.new_window("""
        run 'tmux set -s "@data-#S" "#{e|%:#{e|+:#{E:##{@data-#S#}},1},256}"'
        run 'tmux next-window'
        """))
  def dec(self):
    self.append(self.new_window("""
        run 'tmux set -s "@data-#S" "#{e|%:#{e|+:#{E:##{@data-#S#}},255},256}"'
        run 'tmux next-window'
        """))

  def read(self):
    self.append(self.new_window("""
        run 'tmux set -s "@data-#S" "#{=1:@input}"'
        run 'tmux set -s "@input" "#{=-#{e|-:#{n:@input},1}:#{?#{e|==:#{n:@input},1},0,#{@input}}}"'
        run 'tmux next-window'
        """))
  def write(self):
    self.append(self.new_window("""
        run 'tmux send-keys -t ":=0" "#{a:#{e|+:0,#{E:##{@data-#S#}}}}"'
        run 'tmux set -s "@output" "#{@output}#{a:#{e|+:0,#{E:##{@data-#S#}}}}"'
        run 'tmux next-window'
        """))

  def jump(self, position, foreward):
    if foreward:
      nz, z = self.index + 2, position + 1
    else:
      nz, z = position, self.index + 2

    self.append(self.new_window("""
        run 'tmux select-window -t ":=#{?#{E:##{@data-#S#}},%s,%s}"'
        """ % (nz, z)))


def compile(program):
  output = Program()
  stack = []
  pairs = dict()
  for i, char in enumerate(program):
    if char == '[':
      stack.append(i)
    elif char == ']':
      o = stack.pop()
      pairs[o] = i + 1
      pairs[i] = o + 1
  if len(stack) != 0:
    raise Exception("mismatching brackets")
  for i, char in enumerate(program):
    if char == '+':
      output.inc()
    elif char == '-':
      output.dec()
    elif char == '>':
      output.move_right()
    elif char == '<':
      output.move_left()
    elif char == '.':
      output.write()
    elif char == ',':
      output.read()
    elif char == '[':
      output.jump(pairs[i], True)
    elif char == ']':
      output.jump(pairs[i], False)
  output.append('select-window -t :=0')
  return output.to_string()


program = '++++++++[>++++[>++>+++>+++>+<<<<-]>+>+>->>+[<]<-]>>.>---.+++++++..+++.>>.<-.<.+++.------.--------.>>+.>++.'
comp = compile(program)
print(comp)
with open(sys.argv[1], 'wt') as o:
  o.write(comp)
