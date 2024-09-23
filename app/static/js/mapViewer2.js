var baseMaps = {};
var overlays = {};
var trajectory = null;
var layerControl = null;
var objectDetectionLayer = null;
var objectDetectionLayer_detail = null;
var highlightOpacity = 0.6;

var mapOverlayOpacity = 1.0;

const map = L.map('map',{
	fullscreenControl: true,
	fullscreenControlOptions: {
		position: 'topleft'
	}
});

buildMap();


function buildMap() {
    if (mapsData == null) {
        loadMapsFromServer();
    }

    baseMaps = setupMapBaseLayers();
    overlays = setupMapOverlays();
    dynamicMapOverlays = L.layerGroup([]);

    layerControl = L.control.layers(baseMaps, overlays, {}, {
        collapsed: false
    }).addTo(map);

    trajectory = setupTrajectory();
    setupPanoMarkers();

    overlays[Object.keys(overlays)[0]].addTo(map);
    layerControl.addOverlay(trajectory, 'Trajectory');
    map.fitBounds(trajectory.getBounds());
    setupZoomHome()
    displayWindDirectionOnMap(30);
}


function loadMapsFromServer() {
    $.ajax({
        type: 'GET',
        url: '/maps/{{ project_id }}',
        async: false,
        success: function (data) {
            console.log(data)
            console.log(data.maps)
            maps = data.maps;
        }
    });
}


function setupMapBaseLayers() {
    let mbAttr = 'Map data &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, Imagery © <a href="https://www.mapbox.com/">Mapbox</a>';
    let mbUrl = 'https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token=pk.eyJ1Ijoicm9ibGFidXNlcndocyIsImEiOiJja3VjaXF3d2MxMTN5Mm9tdmQzaGphdGU3In0.BhKF_054bVOPcviIq2yIKg';

    let streets = L.tileLayer(mbUrl, {
        maxZoom: 25,
        id: 'mapbox/streets-v11',
        tileSize: 512,
        zoomOffset: -1,
        attribution: mbAttr
    });

    let osm = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 25,
        attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    });

    const satellite = L.tileLayer(mbUrl, {
        maxZoom: 25,
        id: 'mapbox/satellite-v9',
        tileSize: 512,
        zoomOffset: -1,
        attribution: mbAttr
    });

    satellite.addTo(map);

    let baseLayers = {
        'OpenStreetMap': osm,
        'Streets': streets,
        'Satellite': satellite
    };
    return baseLayers;
}

function setupTrajectory() {
    // data is under flightTrajectory
    let latlngs = [];
    for (let i = 0; i < flightTrajectory.length; i++) {
        latlngs.push([parseFloat(flightTrajectory[i][0]), parseFloat(flightTrajectory[i][1])]);
    }

    trajectory = L.polyline(latlngs, { color: 'fuchsia' });
    trajectory.addTo(map);
    return trajectory;
}


function setupMapOverlays() {
    let overlays = {};
    for (let i = 0; i < mapsData.length; i++) {
        let mapOverlay = mapsData[i];
        let name = mapOverlay.name;
        let layerGroup = setupSingleMap(mapOverlay)
        overlays[name] = layerGroup;
    }
    return overlays;
}

function setupSingleMap(mapOverlay) {
    let bounds = mapOverlay.bounds;
    let corners = mapOverlay.bounds_corners;
    let filename = mapOverlay.file;
    let imageCoords = mapOverlay.image_coordinates;

    if (filename[0] === ".") {
        filename = filename.substring(1);
    }
    
    console.log("corners: " + corners);
    let layer = null;
    if (corners === null || corners === undefined) {
         layer = L.imageOverlay(filename, bounds);
    } else {
        let topleft = corners[3];
        let topright = corners[2];
        let bottomleft = corners[0];
        let bottomright = corners[1];


        layer = L.imageOverlay.rotated(filename, topleft, topright, bottomleft);

        //make a circle for each corner in red, green, blue, yellow
        // let marker1 = L.circle(topleft, { color: 'red', fillColor: 'red', fillOpacity: 1, radius: 4 }).addTo(map);
        // let marker2 = L.circle(topright, { color: 'green', fillColor: 'green', fillOpacity: 1, radius: 4 }).addTo(map);
        // let marker3 = L.circle(bottomleft, { color: 'blue', fillColor: 'blue', fillOpacity: 1, radius: 4 }).addTo(map);
        // let marker4 = L.circle(bottomright, { color: 'yellow', fillColor: 'yellow', fillOpacity: 1, radius: 4 }).addTo(map);
    }

    let layerGroup = L.layerGroup([layer]);

    if (imageCoords != null) {
        loadOutline(mapOverlay, layerGroup);
    }
    return layerGroup
}


function loadOutline(mapOverlay, layerGroup) {

    let polygons = [];
    let coordinates = mapOverlay.image_coordinates;
    let mapSize = mapOverlay.size;
    let bounds = mapOverlay.bounds;
    let lat1 = bounds[0][0];
    let long1 = bounds[0][1];
    let lat2 = bounds[1][0];
    let long2 = bounds[1][1];

    let debug_map= false;


    let debugCoordsGrid = mapOverlay.debug_coords_grid;
    if (debugCoordsGrid != null && debug_map) {
        let grid = L.polygon(debugCoordsGrid, { color: 'black', weight: 1, fillOpacity: 0, opacity: 1 }).addTo(layerGroup);
    }

    for (let i = 0; i < coordinates.length; i++) {
        let coordinates_gps = coordinates[i].coordinates_gps;
        let latlngs = [];
        if (coordinates_gps != null && coordinates_gps != "") {
            latlngs = coordinates_gps;
            //console.log("GPS coordinates found for image " + coordinates[i].file_name);
            //console.log(latlngs);
        } else{
            console.log("No GPS coordinates found for image " + coordinates[i].file_name + "using pixel coodrinated encoded in string");

            var polygonString = coordinates[i].coordinates_string;
            if (polygonString == "") {
                continue;
            }
            var points_strings = polygonString.split(',');
            var points = new Array();

            for (var j = 0; j < points_strings.length; j++) {
                var point = points_strings[j].split(' ');
                points.push([parseInt(point[0]), parseInt(point[1])]);
            }

            if (typeof (mapSize[0]) == 'string') {
                var arr = new Array();
                arr.push(parseInt(mapSize[0]));
                arr.push(parseInt(mapSize[1]));
                mapSize = arr;
            }

            var p1 = [points[0][0] / mapSize[0], points[0][1] / mapSize[1]];
            var p2 = [points[1][0] / mapSize[0], points[1][1] / mapSize[1]];
            var p3 = [points[2][0] / mapSize[0], points[2][1] / mapSize[1]];
            var p4 = [points[3][0] / mapSize[0], points[3][1] / mapSize[1]];
            var pL1 = [p1[1] * lat1 + ((1 - p1[1]) * lat2), p1[0] * long2 + ((1 - p1[0]) * long1)];
            var pL2 = [p2[1] * lat1 + ((1 - p2[1]) * lat2), p2[0] * long2 + ((1 - p2[0]) * long1)];
            var pL3 = [p3[1] * lat1 + ((1 - p3[1]) * lat2), p3[0] * long2 + ((1 - p3[0]) * long1)];
            var pL4 = [p4[1] * lat1 + ((1 - p4[1]) * lat2), p4[0] * long2 + ((1 - p4[0]) * long1)];
            latlngs = [pL1, pL2, pL3, pL4];
        }
        let r = 255-parseInt((i/coordinates.length)*255);
        let g = parseInt((i/coordinates.length)*255);
        let b = Math.max(parseInt((i*2/coordinates.length)*255),  255-parseInt((i*2/coordinates.length)*255));
        let color = 'rgb('+r+','+g+','+b+')';

        var polygon = L.polygon(latlngs, { opacity: 0, fillOpacity: 0.0, fillColor: color });
        polygon.filename = coordinates[i].file_name;
        polygon.on('mouseover', highlightFeatureByEvent);
        polygon.on('mouseout', resetHighlightByEvent);
        polygon.on('click', showImageFromMap);
        layerGroup.addLayer(polygon);

        polygons.push(polygon);

        //debug visualization:
        let orientations = coordinates[i].orientations;
        if (orientations != null && orientations != "" && debug_map) {
            let orientation_gimbal = orientations.gimbal;
            let orientation_flight = orientations.flight;
            let orientation_corrected = orientations.corrected;

            //draw small circle at center
            let center = [(latlngs[0][0] + latlngs[2][0]) / 2, (latlngs[0][1] + latlngs[2][1]) / 2];
            let circle = L.circle(center, { color: 'black', fillColor: 'black', fillOpacity: 1, radius: 2 });
            layerGroup.addLayer(circle);          


            //draw arrow from center in direction of gimbal
            let angle = parseFloat(orientation_gimbal);
            console.log("angle: " + angle);
            let length = 0.000069;
            let dx = length * Math.cos(angle * Math.PI / 180);
            let dy = length * Math.sin(angle * Math.PI / 180);
            console.log("dx: " + dx + " dy: " + dy);
            let x = center[0] + dx;
            let y = center[1] + dy;
            console.log("x: " + x + " y: " + y);
            let arrow = L.polyline([center, [x,y]], { color: 'green' });

            //draw arrow from center in direction of camera
            angle = parseFloat(orientation_flight);
            length = length*1.4;
            dx = length * Math.cos(angle * Math.PI / 180);
            dy = length * Math.sin(angle * Math.PI / 180);
            arrow2 = L.polyline([center, [center[0] + dx, center[1] + dy]], { color: 'red' });
            
            angle = parseFloat(orientation_corrected);
            length = length*1.35;
            dx = length * Math.cos(angle * Math.PI / 180);
            dy = length * Math.sin(angle * Math.PI / 180);
            arrow3 = L.polyline([center, [center[0] + dx, center[1] + dy]], { color: 'blue' });
            
            
            layerGroup.addLayer(arrow);
            layerGroup.addLayer(arrow2);
            layerGroup.addLayer(arrow3);

            
        }


    }

    return polygons;
}

function highlightFeatureByEvent(e) {
    var layer = e.target;
    highlightFeature(layer);
}

function highlightFeature(layer) {
    layer.setStyle({
        fillOpacity: highlightOpacity
    });
}

function resetHighlightByEvent(e) {
    var layer = e.target;
    resetHighlight(layer);
}

function resetHighlight(layer) {
    layer.setStyle({
        fillOpacity: 0.0
    });
}

function showImageFromMap(e) {
    let currentpolygon = e.target;
    showSlideByFilename(currentpolygon.filename);
}

function updateMap(singleMapData, addIfNotFound) {
    let mapName = singleMapData.name;
    console.log("map name:" + mapName);
    console.log(overlays[mapName]);

    for (let i = 0; i < mapsData.length; i++) {
        if (mapsData[i].name === mapName) {
            mapsData[i] = singleMapData;
            
            map.removeLayer(overlays[mapName]);
            overlays[mapName].clearLayers();
            uodatedLayers = setupSingleMap(singleMapData).getLayers();
            for (let j = 0; j < uodatedLayers.length; j++) {
                overlays[mapName].addLayer(uodatedLayers[j]);
            }
            map.addLayer(overlays[mapName]);
            
            return;
        }
    }

    if (addIfNotFound) addMap(singleMapData);
}


function addMap(singleMapData) {
    //check if already available in mapsData, if notadd it
    mapsData.push(singleMapData);

    //check if potential placeholder map needs to be removed

    let name = singleMapData.name;
    let layerGroup = setupSingleMap(singleMapData)
    overlays[name] = layerGroup;
}

function setupZoomHome() {
    let center = map.getCenter();
    let defaultZoom = map.getZoom();

    L.Control.zoomHome = L.Control.extend({
        options: {
            position: 'topleft',
            zoomHomeText: '&#9873;',
            zoomHomeTitle: 'Zoom home'
        },
        onAdd: function (map) {
            var controlName = 'gin-control-zoom',
                container = L.DomUtil.create('div', controlName + ' leaflet-bar'),
                options = this.options;
            this._zoomHomeButton = this._createButton(options.zoomHomeText, options.zoomHomeTitle,
                controlName + '-home', container, this._zoomHome);
            return container;
        },
        onRemove: function (map) {
        },
        _zoomHome: function (e) {
            map.flyTo(center, defaultZoom);
        },
        _createButton: function (html, title, className, container, fn) {
            var link = L.DomUtil.create('a', className, container);
            link.innerHTML = html;
            link.href = '#';
            link.title = title;
            link.role = "button";
            L.DomEvent
                .on(link, 'click', fn, this)
                .on(link, 'click', L.DomEvent.stop)
                .on(link, 'click', this._refocusOnMap, this);;
            return link;
        },
    });


    L.control.scale( {position: 'bottomright'} ).addTo(map);

    let zoomHome = new L.Control.zoomHome();
    zoomHome.addTo(map);
}



//////////////////////////////////////
// Overlay Opacity
//////////////////////////////////////

$('#mapOverlayOpacityRange').on('input', function () {
    changeAlpha($(this).val());
});

function changeAlpha(value) {
    mapOverlayOpacity = value / 100;
    let overlayKeys = Object.keys(overlays);
    for (let i = 0; i < overlayKeys.length; i++) {
        let overlay = overlays[overlayKeys[i]].getLayers()[0];
        overlay.setOpacity(mapOverlayOpacity);
    }
}


$('#mapOverlayStyleCheckbox').change(function () {
    // if (detections != null) {
    //     if (objectDetectionLayer != null) {
    //         generateObjectDetectionLayer(detections);
    //     }
    // }
    if(highlightOpacity === 0.0) {
        highlightOpacity = 0.6;
    } else {
        highlightOpacity = 0.0;
    }
});





//////////////////////////////////////
// Pano Markers
//////////////////////////////////////



function setupPanoMarkers() {
    if (panos == null || panos == "") {
        return;
    }

    for (let i = 0; i < panos.length; i++) {
        let pano = panos[i];
        let coordinates = pano.coordinates;
        if (coordinates == null || coordinates == "" || coordinates.length === 0) {
            continue;
        }

        let marker = L.marker(coordinates, { clickable: true });
        marker.on("click", function (e) { show_pano(i) });
        marker.addTo(map);
    }
}


//////////////////////////////////////
// Wind direction
//////////////////////////////////////

function displayWindDirectionOnMap(angle) {
    let windDir = -1.0;
    let weatherTable = document.getElementById('weatherDataTable');
    for (let i = 0; i < weatherDataTable.rows.length; i++) {
        let title = weatherTable.rows[i].cells[0].innerHTML;
        console.log(title);
        if (title === "Wind Direction") {
            let windDirString = weatherTable.rows[i].cells[1].innerHTML;
            console.log(windDirString);
            windDir = parseFloat(windDirString.split('°')[0]);
            console.log(windDir);
            break;    
        }
    }

    if(windDir===-1.0){
        return;
    }
    let windDirRotation = windDir + 180.0;

    L.LogoControl = L.Control.extend({
        options: {
            position: 'bottomleft'
        },

        onAdd: function (map) {
            var container = L.DomUtil.create('div', 'leaflet-bar leaflet-control logo-control');
            container.classList.add('wind-overlay');
            container.style.borderStyle = 'none';
            var icon = L.DomUtil.create('a', '', container);
            icon.style.display = 'flex';
            icon.style.backgroundColor = 'rgba(0,0,0,0)';
            icon.style.width = '100%';
            icon.style.height = '100%';
            icon.innerHTML = `<img width="100%" class="logo-control-img" src="static/default/arrow-v2.png" style="transform: rotate(${windDirRotation}deg); margin: auto;">`;
            L.DomEvent.disableClickPropagation(icon);
            container.title = `Wind Direction ${windDir}°`;
            1
            return container;
        },
    });

    new L.LogoControl().addTo(map)
}




//////////////////////////////////////
// Object Detection Layer
//////////////////////////////////////



function getSelectedCategories(objectDetectionData) {
    let categoryVisibilities = {};
    for (let i = 0; i < objectDetectionData["categories"].length; i++) {
        let name = objectDetectionData["categories"][i]["name"];
        let checkbox = document.getElementById(name + "-checkbox-map");
        if (checkbox != null) {
            categoryVisibilities[name] = checkbox.checked;
        }
    }
    return categoryVisibilities;
}

function getVisibleObjectTypesPerImage(objectDetectionData) {
    let foundObjectsByImageID = {};
    for (let i = 0; i < objectDetectionData.annotations.length; i++) {
        imageID = objectDetectionData.annotations[i].image_id;
        categoryID = objectDetectionData.annotations[i].category_id;
        score = objectDetectionData.annotations[i].score;
        category = objectDetectionData.categories[categoryID - 1];
        let slider = document.getElementById("slider_" + category.name + "_global_threshold");
        if (slider == null) {
            continue;
        }
        let threshold = slider.value;
        if (score < threshold) {
            continue;
        }

        if (imageID in foundObjectsByImageID) {
            //check if categoryID is already in list
            if (foundObjectsByImageID[imageID].indexOf(categoryID) > -1) {
                continue;
            }
            foundObjectsByImageID[imageID].push(categoryID);
        }
        else {
            foundObjectsByImageID[imageID] = [categoryID];
        }
    }
    return foundObjectsByImageID;
}


function getMapData(mapName) {
    for (let i = 0; i < mapsData.length; i++) {
        let mapOverlay = mapsData[i];
        let name = mapOverlay.name;
        if (name === mapName) {
            return mapOverlay;
        }
    }
    return null;
}

function generateObjectDetectionLayer(objectDetectionData) {
    console.log("!!!!!!!!!----!!!!!!!!!! generateObjectDetectionLayer");
    let mapImagesCoordinates = getMapData("RGB").image_coordinates;
    if (mapImagesCoordinates == null) {
        return;
    }


    let layer_visibility = false;
    if (objectDetectionLayer != null) {
        layer_visibility = map.hasLayer(objectDetectionLayer);
        map.removeLayer(objectDetectionLayer);
        layerControl.removeLayer(objectDetectionLayer);
    }
    else {
        setupObjectDetectionControl()//fix parameters 
    }

    // generate a new layer
    objectDetectionLayer = L.layerGroup();

    let category_visibilities = getSelectedCategories(objectDetectionData);// fix parameters

    //loop over all detections and collect found object types per image using image_id as key
    let foundObjectsByImageID = getVisibleObjectTypesPerImage(objectDetectionData)// fix parameters objectDetectionData

    let rgbMapData = getMapData("RGB");
    let mapSizeRGB = rgbMapData.size;
    let long1RGB = rgbMapData.bounds[0][1];
    let lat1RGB = rgbMapData.bounds[0][0];
    let long2RGB = rgbMapData.bounds[1][1];
    let lat2RGB = rgbMapData.bounds[1][0];


    //now loop over all images and add the fitting marker to the layer
    for (let i = 0; i < mapImagesCoordinates.length; i++) {
        let filename_long = mapImagesCoordinates[i].file_name;
        filename = filename_long.split("/").pop();
        let polygonString = mapImagesCoordinates[i].coordinates_string;
        let points_strings = polygonString.split(',');
        let points = new Array();
        for (let j = 0; j < points_strings.length; j++) {
            let point = points_strings[j].split(' ');
            points.push([parseInt(point[0]), parseInt(point[1])]);
            points[j][0] = (points[j][0] / mapSizeRGB[0] * long2RGB) + ((1 - points[j][0] / mapSizeRGB[0]) * long1RGB);
            points[j][1] = (points[j][1] / mapSizeRGB[1] * lat1RGB) + ((1 - points[j][1] / mapSizeRGB[1]) * lat2RGB);
            //Swap lat and long
            let temp = points[j][0];
            points[j][0] = points[j][1];
            points[j][1] = temp;
        }
        let center = [((points[0][0] + points[2][0]) / 2.0), ((points[0][1] + points[2][1]) / 2.0)];

        let imageID = -1;
        images = objectDetectionData.images;
        //get image.id from images
        for (let j = 0; j < images.length; j++) {
            if (images[j].file_name == filename) {
                imageID = images[j].id;
                break;
            }
        }
        if (imageID == -1) {
            //add white circle as marker
            marker = L.circle(center, {
                color: 'white',
                fillColor: 'white',
                fillOpacity: 0.5,
                radius: 2
            }).addTo(map);

            continue;
        }
        let icon_filename = ''
        //add an image marker based on the found object categories
        if (imageID in foundObjectsByImageID) {
            foundCategoriesInImage = foundObjectsByImageID[imageID];
            if (foundCategoriesInImage.indexOf(1) > -1) {
                if (category_visibilities['fire']) {
                    icon_filename = icon_filename + 'Brand';
                }
            }
            if (foundCategoriesInImage.indexOf(2) > -1) {
                if (category_visibilities['vehicle']) {
                    icon_filename = icon_filename + 'Fahrzeug';
                }
            }
            if (foundCategoriesInImage.indexOf(3) > -1) {
                if (category_visibilities['human']) {
                    icon_filename = icon_filename + 'Person';
                }
            }
        }

        if (icon_filename == '') {
            //add white circle as marker
            marker = L.circle(center, {
                color: 'white',
                fillColor: 'white',
                fillOpacity: 0.5,
                radius: 2
            }).addTo(objectDetectionLayer);
            continue;
        }

        // checkbox = document.getElementById("mapOverlayStyleCheckbox");
        // if (checkbox.checked) {
        //     detectionIconStyleSetting = 'icon'; //'taktischeZeichen' or 'icon'
        //     detectionIconSize = 50;
        // }
        // else {
        //     detectionIconStyleSetting = 'taktischeZeichen'; //'taktischeZeichen' or 'icon'
        //     detectionIconSize = 40;
        // }
        let detectionIconStyleSetting = 'icon'; //'taktischeZeichen' or 'icon'
        let detectionIconSize = 50;
        

        marker = L.marker(center, {
            icon: L.icon({
                iconUrl: '/static/default/signs/' + detectionIconStyleSetting + '/' + icon_filename + '.png',
                iconSize: [detectionIconSize, detectionIconSize],
                iconAnchor: [detectionIconSize / 2, detectionIconSize / 2],
                popupAnchor: [0, 0],
                shadowUrl: null,
                shadowSize: null,
                shadowAnchor: null
            })
        });
        marker.on('click', function () { showSlideByFilename(filename_long) });
        marker.addTo(objectDetectionLayer);
    }

    //add layer to map
    if (layer_visibility) {
        objectDetectionLayer.addTo(map);
    }
    layerControl.addOverlay(objectDetectionLayer, 'taktischeZeichen');
    draw_individual_objects_on_map(objectDetectionData);
}

function setupObjectDetectionControl(objectDetectionData) {
    const ObjectDetectionControl = L.Control.extend({
        options: {
            detections: {}
        },

        initialize: function (options) {
            L.Util.setOptions(this, options);
        },

        onAdd: function (map) {
            const container = L.DomUtil.create('div', 'custom-control');

            let htmlContent = `
                <div class="leaflet-control-layers leaflet-touch">
                <a id="map-overlay-detections-filter-activator" class="leaflet-control-layers-toggle" title="detections" href="#" style="background-image: url(/static/default/ObjectDetectionIcon.png); background-repeat: no-repeat; background-size: 80%;"></a>
                <div id="map-overlay-detections-filter-expanded" class="leaflet-control-layers-expanded leaflet-control-layers" style="display:none";>
                <section class="leaflet-control-layers-list">
                `;
            for (var i = 0; i < detections["categories"].length; i++) {
                let name = detections["categories"][i]["name"];
                //try to get the global slider, if it does not exist, skip this category
                if (document.getElementById("slider_" + name + "_global_threshold")) {
                    htmlContent += `
                        <div style="display: flex; width: 100%">
                            <input type="checkbox" id="${name}-checkbox-map"}>
                            <label for="${name}-checkbox-map">${name}</label>
                            <input type="range" id="${name}-slider-map" min="0" max="1" step="0.01" value="0.75" style="width:150px; margin-left: auto;">
                        </div>
                        `;
                }
            }
            htmlContent += `
            </section>
            </div>
            </div>
            `;


            container.innerHTML = htmlContent;

            // Prevent map click events from being triggered on the control container
            L.DomEvent.disableClickPropagation(container);

            // add on mouseenter event to show the expanded filter
            L.DomEvent.on(container.querySelector('#map-overlay-detections-filter-activator'), 'mouseenter', function () {
                container.querySelector('#map-overlay-detections-filter-expanded').style.display = 'block';
                container.querySelector('#map-overlay-detections-filter-activator').style.display = 'none';
            });

            // add on mouseleave event to hide the expanded filter
            L.DomEvent.on(container.querySelector('#map-overlay-detections-filter-expanded'), 'mouseleave', function () {
                container.querySelector('#map-overlay-detections-filter-expanded').style.display = 'none';
                container.querySelector('#map-overlay-detections-filter-activator').style.display = 'block';
            });

            // Event listeners for checkbox and slider changes
            for (var i = 0; i < detections["categories"].length; i++) {
                let name = detections["categories"][i]["name"];

                if (document.getElementById("slider_" + name + "_global_threshold")) {
                    //Set checkbox to be checked by default
                    container.querySelector(`#${name}-checkbox-map`).checked = true;
                    L.DomEvent.on(container.querySelector(`#${name}-checkbox-map`), 'change', this.toggleVisibilityDetection, this);
                    L.DomEvent.on(container.querySelector(`#${name}-slider-map`), 'input', this.updateThresholdDetection, this);
                }
            }

            return container;
        },

        toggleVisibilityDetection: function (event) {
            draw_individual_objects_on_map(detections);
        },

        updateThresholdDetection: function (event) {

            let name = event.target.id.split("-")[0];
            global_slider = document.getElementById("slider_" + name + "_global_threshold");
            global_slider.value = event.target.value;
            global_slider.dispatchEvent(new Event('change', { bubbles: true }));

        }
    });

    (new ObjectDetectionControl(objectDetectionData)).addTo(map);
}



function draw_individual_objects_on_map(objectDetectionData) {
    console.log("!!!!!!!!!----!!!!!!!!!! draw_individual_objects_on_map");
    //check if Layer already exists
    if (objectDetectionLayer_detail != null) {
        map.removeLayer(objectDetectionLayer_detail);
        //layerControl2.removeLayer(objectDetectionLayer_detail);
    }

    let rgbMapData = getMapData('RGB');

    objectDetectionLayer_detail = L.layerGroup();
    objectDetectionLayer_detail.addTo(map);

    let detections = objectDetectionData.annotations;
    let images = objectDetectionData.images;

    global_thresholds = get_global_thresholds();
    let category_visibilities = {};

    for (var i = 0; i < objectDetectionData["categories"].length; i++) {
        let name = objectDetectionData["categories"][i]["name"];
        var checkbox = document.getElementById(name + "-checkbox-map");
        if (checkbox != null) {
            category_visibilities[name] = checkbox.checked;
        }
    }




    for (var i = 0; i < detections.length; i++) {
        let detection = detections[i];
        let categoryID = detection.category_id;
        let imageID = detection.image_id;
        let category = objectDetectionData["categories"][detection.category_id - 1]["name"];
        let score = detection.score;


        if (category_visibilities[category] == false) {
            continue;
        }

        if (score < global_thresholds[categoryID - 1]) {
            continue;
        }

        let image = images[detection.image_id];
        let filename = image.file_name;
        let image_size = [image.width, image.height];
        let object_bounds = detection.bbox;
        let object_center_gps = detection.gps_coords;
        let ringcolor = 'grey';
        
        if (object_center_gps == null || object_center_gps == "" || object_center_gps == undefined) {
            object_center_gps = get_object_detection_coordinate(filename, object_bounds, image_size, detection.image_id, rgbMapData);
            detection.gps_coords = object_center_gps;
        }
        else {
            ringcolor = 'white';
        }
            

        if (object_center_gps == null) {
            continue;
        }

        let color = 'white';
        if (categoryID == 1) {
            color = 'red';
        }
        else if (categoryID == 2) {
            color = 'black';
        }
        else if (categoryID == 3) {
            color = 'blue';
        }

        marker = L.circle(object_center_gps, {
            color: ringcolor,
            fillColor: color,
            fillOpacity: 0.8,
            radius: 1.5
        }).addTo(objectDetectionLayer_detail);

        marker.on('click', function () { showImageByFileName(filename) });
    }


    //layerControl2.addOverlay(objectDetectionLayer_detail , 'taktischeZeichen_positioniert');
}


function get_object_detection_coordinate(filename, object_bounds, image_size, image_id, rgbMapData) {
    let mapSizeRGB = rgbMapData.size;
    let long1RGB = rgbMapData.bounds[0][1];
    let lat1RGB = rgbMapData.bounds[0][0];
    let long2RGB = rgbMapData.bounds[1][1];
    let lat2RGB = rgbMapData.bounds[1][0];
    let mapImagesCoordinates = rgbMapData.image_coordinates;

    image_index = -1;

    if (mapImagesCoordinates.length > image_id) {
        let long_name = mapImagesCoordinates[image_id].file_name;
        let short_name = long_name.split("/").pop();
        if (short_name == filename) {
            image_index = image_id;
        }
    }

    if (image_index == -1) {
        for (var i = 0; i < mapImagesCoordinates.length; i++) {
            let long_name = mapImagesCoordinates[i].file_name;
            let short_name = long_name.split("/").pop();
            if (short_name == filename) {
                image_index = i;
                break;
            }
        }
    }

    if (image_index == -1) {
        return null;
    }

    let coordinates_string = mapImagesCoordinates[image_index].coordinates_string;
    let coordinates_corners = mapImagesCoordinates[image_index].coordinates_gps;

    if (coordinates_corners === null || coordinates_corners === undefined) {
            

        let points_strings = coordinates_string.split(',');
        let image_bounds_gps = new Array();

        for (var j = 0; j < points_strings.length; j++) {
            let point = points_strings[j].split(' ');
            image_bounds_gps.push([parseInt(point[0]), parseInt(point[1])]);
            image_bounds_gps[j][0] = (image_bounds_gps[j][0] / mapSizeRGB[0] * long2RGB) + ((1 - image_bounds_gps[j][0] / mapSizeRGB[0]) * long1RGB);
            image_bounds_gps[j][1] = (image_bounds_gps[j][1] / mapSizeRGB[1] * lat1RGB) + ((1 - image_bounds_gps[j][1] / mapSizeRGB[1]) * lat2RGB);
            //Swap lat and long
            let temp = image_bounds_gps[j][0];
            image_bounds_gps[j][0] = image_bounds_gps[j][1];
            image_bounds_gps[j][1] = temp;
        }

        let object_center_gps = new Array();

        let object_center_px = [object_bounds[0] + 0.5 * object_bounds[2], object_bounds[1] + 0.5 * object_bounds[3]];
        let factor_w = 1 - (object_center_px[0] / image_size[0]);
        let factor_h = 1 - (object_center_px[1] / image_size[1]);


        let u = [image_bounds_gps[3][0] - image_bounds_gps[0][0], image_bounds_gps[3][1] - image_bounds_gps[0][1]];
        let v = [image_bounds_gps[1][0] - image_bounds_gps[0][0], image_bounds_gps[1][1] - image_bounds_gps[0][1]];

        object_center_gps.push(image_bounds_gps[0][0] + (u[0] * factor_w) + (v[0] * factor_h));
        object_center_gps.push(image_bounds_gps[0][1] + (u[1] * factor_w) + (v[1] * factor_h));


        return object_center_gps;
    } else {
        let topleft = coordinates_corners[0];
        let topright = coordinates_corners[1];
        let bottomright = coordinates_corners[2];
        let bottomleft = coordinates_corners[3];

        let object_center_px = [object_bounds[0] + 0.5 * object_bounds[2], object_bounds[1] + 0.5 * object_bounds[3]];
        let factor_w = object_center_px[0] / image_size[0];
        let factor_h = object_center_px[1] / image_size[1];

        let u1 = [topright[0] - topleft[0], topright[1] - topleft[1]];
        let u2 = [bottomright[0] - bottomleft[0], bottomright[1] - bottomleft[1]];

        u1 = [topleft[0]    + u1[0] * factor_w, topleft[1]    + u1[1] * factor_w];
        u2 = [bottomleft[0] + u2[0] * factor_w, bottomleft[1] + u2[1] * factor_w];

        let v = [u2[0] -  u1[0], u2[1] - u1[1]];


        let object_center_gps = new Array();
        object_center_gps.push((v[0] * factor_h) + (u1[0]));
        object_center_gps.push((v[1] * factor_h) + (u1[1]));

        return object_center_gps;
    }

}





//////////////////////////////////////
// functions related to map content, but not the leaflet map itself
//////////////////////////////////////


function isUsedInMap(index, displayingIR) {
    console.log("isUsedInMap ?");
    var filename = "";
    if (displayingIR) {
        filename = getFilePathBySlideIndex(index, 1);
    }
    else {
        filename = getFilePathBySlideIndex(index, 0);
    }

    for (var i = 0; i < mapsData.length; i++) {
        let list = mapsData[i].image_coordinates;
        if (list == null || list == "") continue;
        return list.some(item => item.file_name === filename);
    }
    return false;
}