let num = 16839;
let dup = num ;
let rev = 0 , dig = 0;

while (num > 0 ) {
  dig = num % 10 ;
  rev = rev * 10 + dig ;
  num /= 10;

}

console.log(dup);
console.log(rev);
