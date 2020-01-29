function get_links (entity) {
    console.log(entity);
};


function enum_entity (entity_list, inspect_name) {
    var inspect = document.getElementById(inspect_name);
    var ul_elem = document.createElement("ul");

    inspect.innerHTML = "";
    inspect.appendChild(ul_elem);

    for (i = 0; i < entity_list.length; i++) { 
	var entity = entity_list[i][0];
	var impact = entity_list[i][1];
	var label = entity_list[i][2];
	var title = entity_list[i][3];

	var li_elem = document.createElement("li");
	li_elem.innerHTML = `<a href="#" title="${title}" onclick="get_links(${entity})">${label}</a>`
	ul_elem.appendChild(li_elem);
    }
};


function run_query () {
    var radius = document.forms.query.radius.value;
    var entity = document.forms.query.entity.value;
    var url = `/api/v1/query/${radius}/`.concat(encodeURI(entity));

    var xhr = new XMLHttpRequest();
    xhr.responseType = "json";
    xhr.open("GET", url);
    xhr.send();

    xhr.onload = function() {
	if (xhr.status != 200) {
	    alert(`Error ${xhr.status}: ${xhr.statusText}`); // e.g. 404: Not Found
	} else { // use the result
	    var obj = xhr.response;
	    console.log(obj);

	    enum_entity(obj.auth, "inspect-authors");
	    enum_entity(obj.pubs, "inspect-publications");
	    enum_entity(obj.jour, "inspect-journals");
	    enum_entity(obj.data, "inspect-datasets");
	    enum_entity(obj.prov, "inspect-providers");
	}
    };

    xhr.onerror = function() {
	alert("API request failed");
    };
};
