var data = [ 1 , 20 , 15 , 6 ];


let i , j;
for(i = 0 ; i < 4 ; i++) {
    for(j = 0 ; j < 4 - 1 - i ; j++){
        if(data[j] > data[j+1]){
            let temp = data[j];
            data[j] = data[j+1];
            data[j+1] = temp;
        }
    }


}

let  k ;
for(k = 0 ; k < 4 ; k++){
    console.log(data[k]);
}