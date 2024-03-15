# Compiling code to tmux

Read more about it on [my blog](https://willhbr.net).

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
