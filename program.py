def is_prime(num):
  i = 2
  while i < num:
    if num % i == 0:
      return 0
    i = i + 1

  return 1

print(is_prime(13))
