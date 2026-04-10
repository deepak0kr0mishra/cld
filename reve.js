var num = 16839;
let dup = num ;
var rev = 0 ;

while (num > 0 ) {
  var dig = 0;
  dig = num % 10 ;
  rev =( rev * 10 )+ dig ;
  num /= 10;

}

console.log(dup);
console.log(rev);
