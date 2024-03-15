# Compiling code to tmux

Read more about it on [my blog](https://willhbr.net/2024/03/15/making-a-compiler-to-prove-tmux-is-turing-complete/) or [watch a demo](https://youtu.be/6V3KnjiBuhU).

Usage for Python:

```shell
python main.py $input $output
./tmux -f $output a -t main
```

Usage for Brainfuck:

```shell
python brainfuck.py $input $output
./tmux -f $output a
```

This is tested using tmux version 3.3a on Ubuntu 23.04.
