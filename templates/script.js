var catch_token = "";


function fetch_graph () {
    var url = `/api/v1/graph/${cache_token}`;
    console.log(url);

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

	    var view = document.getElementById("view_graph");
	    view.innerHTML = obj;
	}
    };

    xhr.onerror = function() {
	alert("API request failed");
    };
};


function get_links (index) {
    var url = `/api/v1/links/${index}`;
    console.log(url);

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

	    var view = document.getElementById("view_links");
	    view.innerHTML = obj;
	}
    };

    xhr.onerror = function() {
	alert("API request failed");
    };
};


function enum_entity (entity_list, neighbor_name) {
    var neighbor = document.getElementById(neighbor_name);
    var ul_elem = document.createElement("ul");

    neighbor.innerHTML = "";
    neighbor.appendChild(ul_elem);

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

	    cache_token = obj.toke;

	    enum_entity(obj.auth, "neighbor-authors");
	    enum_entity(obj.pubs, "neighbor-publications");
	    enum_entity(obj.jour, "neighbor-journals");
	    enum_entity(obj.data, "neighbor-datasets");
	    enum_entity(obj.prov, "neighbor-providers");

	    fetch_graph();
	}
    };

    xhr.onerror = function() {
	alert("API request failed");
    };
};


function open_view (view_name) {
    var tabcontent = document.getElementsByClassName("tabcontent");

    for (i = 0; i < tabcontent.length; i++) {
	tabcontent[i].style.display = "none";
    }

    document.getElementById(view_name).style.display = "block";
};


// the following runs as soon as the page loads...

(function () {
    open_view("view_links");
})();
