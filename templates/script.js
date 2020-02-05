var cache_token = "";


function fetch_graph_html () {
    var url = `/graph/${cache_token}`;
    var html = `<iframe name="frame" src="${url}" frameborder="0" scrolling="no"></iframe>`;
    var view = document.getElementById("view_graph");
    view.innerHTML = html;
};


function get_links (index) {
    var url = `/api/v1/links/${index}`;
    var xhr = new XMLHttpRequest();
    xhr.responseType = "json";
    xhr.open("GET", url);
    xhr.send();

    xhr.onload = function() {
	if (xhr.status != 200) {
	    alert(`Error ${xhr.status}: ${xhr.statusText}`); // e.g. 404: Not Found
	} else { // use the result
	    var obj = xhr.response;
	    var view = document.getElementById("view_links");
	    view.innerHTML = obj;
	    open_view("view_links");
	};
    };

    xhr.onerror = function() {
	alert("API request failed");
    };
};


function enum_hood (entity_list, neighbor_name) {
    var neighbor = document.getElementById(neighbor_name);
    var ul_elem = document.createElement("ul");
    neighbor.innerHTML = "";
    neighbor.appendChild(ul_elem);

    for (i = 0; i < entity_list.length; i++) { 
	var entity = entity_list[i][0];
	var impact = entity_list[i][1];
	var label = entity_list[i][2];
	var title = entity_list[i][3];
	var shown = entity_list[i][4];

	if (shown) {
	    var li_elem = document.createElement("li");
	    li_elem.innerHTML = `<a href="#" title="${title}" onclick="get_links(${entity})">${label}</a>`;
	    ul_elem.appendChild(li_elem);
	};
    };
};


function run_query () {
    var entity = document.forms.query.entity.value;
    var radius = document.forms.query.radius.value;
    return run_query_param(entity, radius);
};


function run_query_string (entity, radius) {
    document.forms.query.entity.value = entity;
    document.forms.query.radius.value = radius;
    return run_query_param(entity, radius);
};


function run_query_param (entity, radius) {
    var url = `/api/v1/query/${radius}/`.concat(encodeURI(entity));
    console.log(url);

    var xhr = new XMLHttpRequest();
    xhr.responseType = "json";
    xhr.open("GET", url);

    document.body.style.cursor = "wait";
    xhr.send();

    xhr.onload = function() {
	if (xhr.status != 200) {
	    alert(`Error ${xhr.status}: ${xhr.statusText}`); // e.g. 404: Not Found
	} else { // use the result
	    var obj = xhr.response;
	    cache_token = obj.toke;

	    enum_hood(obj.auth, "neighbor-authors");
	    enum_hood(obj.pubs, "neighbor-publications");
	    enum_hood(obj.jour, "neighbor-journals");
	    enum_hood(obj.data, "neighbor-datasets");
	    enum_hood(obj.prov, "neighbor-providers");

	    fetch_graph_html();
	    document.body.style.cursor = "default";
	};
    };

    xhr.onerror = function() {
	alert("API request failed");
    };

    return true;
};


function open_view (view_name) {
    var tabcontent = document.getElementsByClassName("tabcontent");

    for (i = 0; i < tabcontent.length; i++) {
	tabcontent[i].style.display = "none";
    };

    document.getElementById(view_name).style.display = "block";

    var tabs = document.getElementsByClassName("pure-menu-item");

    for (i = 0; i < tabs.length; i++) {
	tabs[i].classList.remove("pure-menu-selected");
    };

    var tab = document.getElementById("tab_".concat(view_name));

    tab.classList.toggle("pure-menu-selected");
};


// the following runs as soon as the page loads...

(function () {
    open_view("view_graph");
})();
