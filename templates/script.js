function run_query() {
  var radius = document.forms.query.radius.value;
  var entity = document.forms.query.entity.value;
  console.log(radius);
  console.log(entity);

  var url = `/api/v1/query/${radius}/`.concat(encodeURI(entity));
  console.log(url);

  var xhr = new XMLHttpRequest();
  xhr.responseType = "json";
  xhr.open("GET", url);
  xhr.send()

  xhr.onload = function() {
    if (xhr.status != 200) {
      alert(`Error ${xhr.status}: ${xhr.statusText}`); // e.g. 404: Not Found
    } else { // use the result
      var obj = xhr.response;
      console.log(obj);
    }
  };

  xhr.onerror = function() {
    alert("API request failed");
  };
}
