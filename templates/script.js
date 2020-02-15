//////////////////////////////////////////////////////////////////////
// analytics view

var cache_token = "";


function fetch_graph_html () {
    const url = `/graph/${cache_token}`;
    const html = `<iframe id="f" name="f" src="${url}" frameborder="0" scrolling="no"></iframe>`;
    const view = document.getElementById("view_graph");
    view.innerHTML = html;
};


function get_links (index) {
    const url = `/api/v1/links/${index}`;
    const xhr = new XMLHttpRequest();
    xhr.responseType = "json";
    xhr.open("GET", url);
    xhr.send();

    xhr.onload = function() {
	if (xhr.status != 200) {
	    alert(`Error ${xhr.status}: ${xhr.statusText}`); // e.g. 404: Not Found
	} else { // use the result
	    const obj = xhr.response;
	    const view = document.getElementById("view_links");
	    view.innerHTML = obj;
	    open_view("view_links");
	};
    };

    xhr.onerror = function() {
	alert("API request failed");
    };
};


function enum_hood (entity_list, neighbor_name) {
    const neighbor = document.getElementById(neighbor_name);
    const ul_elem = document.createElement("ul");
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


function run_query_form () {
    const entity = document.forms.query.entity.value;
    const radius = document.forms.query.radius.value;
    return run_query(entity, radius);
};


function run_query_string (entity, radius) {
    document.forms.query.entity.value = entity;
    document.forms.query.radius.value = radius;
    return run_query(entity, radius);
};


function run_query (entity, radius) {
    const url = `/api/v1/query/${radius}/`.concat(encodeURI(entity));
    //console.log(url);

    const xhr = new XMLHttpRequest();
    xhr.responseType = "json";
    xhr.open("GET", url);

    document.body.style.cursor = "wait";
    xhr.send();

    xhr.onload = function() {
	if (xhr.status != 200) {
	    alert(`Error ${xhr.status}: ${xhr.statusText}`); // e.g. 404: Not Found
	} else { // use the result
	    const obj = xhr.response;
	    cache_token = obj.toke;

	    enum_hood(obj.auth, "neighbor-auth");
	    enum_hood(obj.publ, "neighbor-publ");
	    enum_hood(obj.jour, "neighbor-jour");
	    enum_hood(obj.data, "neighbor-data");
	    enum_hood(obj.prov, "neighbor-prov");

	    fetch_graph_html();
	    document.body.style.cursor = "default";
	};
    };

    xhr.onerror = function() {
	alert("API request failed");
    };

    // update the browser history
    document.title = `Rich Contex: @${radius} / ${entity}`;
    shareable_url = `/?radius=${radius}&entity=${entity}`;

    history.pushState({ id: "homepage" },
		      document.title,
		      shareable_url
		      );

    return true;
};


function open_view (view_name) {
    const tabcontent = document.getElementsByClassName("tabcontent");

    for (i = 0; i < tabcontent.length; i++) {
	if (tabcontent[i].style) {
	    tabcontent[i].style.display = "none";
	};
    };

    const view = document.getElementById(view_name);

    if (view) {
	view.style.display = "block";
    };

    const tabs = document.getElementsByClassName("pure-menu-item");

    for (i = 0; i < tabs.length; i++) {
	if (tabs[i] && tabs[i].classList) {
	    tabs[i].classList.remove("pure-menu-selected");
	};
    };

    const tab = document.getElementById("tab_".concat(view_name));

    if (tab) {
	tab.classList.toggle("pure-menu-selected");
    };
};


function conf_web_token () {
    const url = "/api/v1/conf_web_token/";
    const xhr = new XMLHttpRequest();
    xhr.responseType = "json";
    xhr.open("POST", url, true);

    const token = document.forms.settings.token.value;
    const data = new FormData();
    data.append("token", token);
    xhr.send(data);

    xhr.onload = function() {
	if (xhr.status != 200) {
	    alert(`Error ${xhr.status}: ${xhr.statusText}`); // e.g. 404: Not Found
	} else { // use the result
	    const obj = xhr.response;
	    const status = document.getElementById("conf_token_status");
	    status.innerHTML = obj;

	    document.forms.settings.token.readOnly = true;

	    const button = document.getElementById("set_web_token");
	    button.disabled = true;
	};
    };

    xhr.onerror = function() {
	alert("API request failed");
    };
};


//////////////////////////////////////////////////////////////////////
// autocomplete

function load_phrases (input_elem, selection_callback) {
    const url = "/api/v1/phrases";
    const xhr = new XMLHttpRequest();
    xhr.responseType = "json";
    xhr.open("GET", url);
    xhr.send();

    xhr.onload = function() {
	if (xhr.status != 200) {
	    alert(`Error ${xhr.status}: ${xhr.statusText}`); // e.g. 404: Not Found
	} else { // use the result
	    // autocomplete for search bar
	    phrases = xhr.response;
	    autocomplete(input_elem, phrases, selection_callback);
	};
    };

    xhr.onerror = function() {
	alert("API request failed");
    };
};


// take action on an autocompleted selection

function selection_callback (phrase) {
    const radius = document.forms.query.radius.value;
    return run_query(phrase.text, radius);
};


// autocomplete takes two arguments, the text field element and an
// array of possible autocompleted values

function autocomplete (input_elem, phrases, callback) {
    var currentFocus;

    // execute a function when someone writes in the text field
    input_elem.addEventListener("input", function(e) {
	var val = this.value;

	// close any already open lists of autocompleted values
	closeAllLists();
	currentFocus = -1;

	if (!val) return false;

	// create a DIV element that will contain the items (values)
	var a = document.createElement("div");
	a.setAttribute("id", this.id + "autocomplete-list");
	a.setAttribute("class", "autocomplete-items");

	// append the DIV element as a child of the autocomplete
	// container
	this.parentNode.appendChild(a);

	for (var i = 0; i < phrases.length; i++) {
	    // check if the item starts with the same letters as the
	    // text field value
	    if (phrases[i].text.substr(0, val.length).toUpperCase() == val.toUpperCase()) {
		// create a DIV element for each matching element
		var b = document.createElement("div");

		// make the matching letters bold
		b.innerHTML = "<strong>" + phrases[i].text.substr(0, val.length) + "</strong>";
		b.innerHTML += phrases[i].text.substr(val.length);

		// insert a input field that will hold the current
		// array item's value
		b.innerHTML += "<input type='hidden' value='" + i + "'>";

		// execute a function when someone clicks on the item
		// value (DIV element)
		b.addEventListener("click", function(e) {
		    // insert the value for the autocomplete text field
		    const i = this.getElementsByTagName("input")[0].value;
		    input_elem.value = phrases[i].text;
		    selection_callback(phrases[i]);

		    // close the list of autocompleted values, or any
		    // other open lists of autocompleted values
		    closeAllLists();
		});

		a.appendChild(b);
	    };
	};
});


// execute a function presses a key on the keyboard

input_elem.addEventListener("keydown", function(e) {
    var x = document.getElementById(this.id + "autocomplete-list");

    if (x) x = x.getElementsByTagName("div");

    if (e.keyCode == 40) {
        // if the arrow DOWN key is pressed, increase the currentFocus
        // variable
        currentFocus++;

        // and and make the current item more visible
        addActive(x);
    } else if (e.keyCode == 38) {
        // if the arrow UP key is pressed, decrease the currentFocus
        // variable
        currentFocus--;

        // and and make the current item more visible
        addActive(x);
    } else if (e.keyCode == 13) {
        // if the ENTER key is pressed, prevent the form from being
        // submitted
        e.preventDefault();

        if (currentFocus > -1) {
	    // and simulate a click on the "active" item
	    if (x) x[currentFocus].click();
        };
    };
});


// a function to classify an item as "active"

function addActive (x) {
    if (!x) return false;

    // start by removing the "active" class on all items
    removeActive(x);

    if (currentFocus >= x.length) currentFocus = 0;

    if (currentFocus < 0) currentFocus = (x.length - 1);

    // add class "autocomplete-active"
    x[currentFocus].classList.add("autocomplete-active");
};


// a function to remove the "active" class from all autocomplete
// items

function removeActive (x) {
    for (var i = 0; i < x.length; i++) {
	x[i].classList.remove("autocomplete-active");
    };
};


// close all autocomplete lists in the document, except the one passed
// as an argument

function closeAllLists (elem) {
    var x = document.getElementsByClassName("autocomplete-items");

    for (var i = 0; i < x.length; i++) {
	if (elem != x[i] && elem != input_elem) {
	    x[i].parentNode.removeChild(x[i]);
	};
    };
};


// execute when someone clicks elsewhere in the document

document.addEventListener("click", function (e) {
    closeAllLists(e.target);
});
};


// the following runs as soon as the page loads...

(function () {
    open_view("view_graph");

    const input_elem = document.getElementsByName("entity")[0];

    if (input_elem) {
	load_phrases(input_elem, selection_callback);
    };
})();
