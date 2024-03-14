def is_prime(num):
  i = 2
  while i < num:
    if num % i == 0:
      return 0
    i = i + 1

  return 1

if is_prime(13):
  print("13 is prime!")
else:
  print("not prime :(")
