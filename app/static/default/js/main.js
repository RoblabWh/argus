'use strict';
const GLOBAL_SCALE = 50;

let scene, camera, renderer;


/* Color setting*/
const CURRENT_FRAME_COLOR = "rgb(0,192,0)";
const KEYFRAME_COLOR = "rgb(92, 85, 250)";
const HIGHLIGHT_COLOR = "rgb(0, 255, 255)";
const EDGE_COLOR = "rgb(192, 223, 255)";
const BACKGROUND_COLOR = "rgb(255, 255, 255)";
const REFERENCE_POINT_COLOR = [255, 0, 0];
const MAPPING_INITIAL_SIZE = 300;

// timestamp on received for measuring fps;
let receiveTimestamp = 0;

let property = {
    CameraMode: 'Follow',
    FixAngle: false,
    LandmarkSize: 0.6,
    KeyframeSize: 0.5,
    CurrentFrameSize: 1.0,
    DrawGraph: true,
    DrawGrid: true,
    DrawPoints: true,
    LocalizationMode: false,
    ResetSignal: function () { },
    StopSignal: function () { }
};

let clock = new THREE.Clock();

let cameraFrames = new CameraFrames();

let pointUpdateFlag = false;
let pointCloud = new PointCloud();

let grid;

let mouseHandler;
let wheelHandler;
let viewControls;


function init() {

    // create a camera
    camera = new THREE.PerspectiveCamera(45, document.getElementsByClassName('vslam_model')[0].offsetWidth / document.getElementsByClassName('vslam_model')[0].offsetHeight, 0.01, 5000);

    //initGui();
    initProtobuf();

    // create a scene, that holds all elements such as cameras and points.
    scene = new THREE.Scene();

    // create a render and set the setSize
    renderer = new THREE.WebGLRenderer({ antialias: false });
    renderer.setClearColor(new THREE.Color(BACKGROUND_COLOR));
    renderer.setSize(document.getElementsByClassName('vslam_model')[0].offsetWidth, document.getElementsByClassName('vslam_model')[0].offsetHeight);
    console.log(document.getElementsByClassName('vslam_model')[0].offsetWidth, document.getElementsByClassName('vslam_model')[0].offsetHeight);

    // create grid plane
    //grid = new THREE.GridHelper(500, 50);
    //scene.add(grid);

    // position and point the camera to the center of the scene
    camera.position.x = -100;
    camera.position.y = 60;
    camera.position.z = 30;
    camera.rotation.x = 0;
    camera.rotation.y = 0;
    camera.rotation.z = 0;

    let lineGeo = new THREE.Geometry();
    for (let i = 0; i < 16; i++) {
        lineGeo.vertices.push(new THREE.Vector3(0, 0, 0));
    }

    // add the output of the renderer to the html element
    // this line must be before initialization TrackBallControls(othrewise, dat.gui won't be work).
    document.getElementById("WebGL-output").appendChild(renderer.domElement);

    // create a view controller that
    viewControls = new ViewControls(camera);

    setCameraMode(property.CameraMode);
    viewControls.update(100);

    // animation render function
    render();
}

function loadKeyframes(keyframes) {
    var keyfrmOutput = [];
    for (let keyfrm of keyframes) {
        let keyframe = {};
        keyframe["id"] = keyfrm.id;
        if (keyfrm.pose != undefined) {
            keyframe["camera_pose"] = [];
            array2mat44(keyframe["camera_pose"], keyfrm.pose);
        }
        keyfrmOutput.push(keyframe);
    }
    for (let keyfrm of keyfrmOutput) {
        let id = keyfrm["id"];
        if (keyfrm["camera_pose"] == undefined) {
            cameraFrames.removeKeyframe(id);
        }
        else {
            cameraFrames.updateKeyframe(id, keyfrm["camera_pose"]);
        }
    }
}

function loadMappingResultSocketViewer(imgUrl, imgHeight, imgWidth, imgVertices) {
    setCameraMode('Bird');
    //get first and last entry of mapped img vertices
    let firstEntry, furthestEntry, distance, lowest_pose;
    distance = 0;
    lowest_pose = 0;
    for (const[id, vertice] of Object.entries(imgVertices)) {
        if (typeof firstEntry == 'undefined') {
            firstEntry = {id, vertice};
        }
        let pose = cameraFrames.getKeyframeOrigin(id);
        if (pose[1] > lowest_pose) {
            lowest_pose = pose[1];
        }
        let poseVector = new THREE.Vector3(pose[0], pose[1], pose[2]);
        if (poseVector.length() > distance) {
            furthestEntry = {id, vertice};
            distance = poseVector.length();
        }
    }
    //get the center of the first and last vertices in image coordinate system
    let firstEntryInImage = Array(2);
    firstEntryInImage[0] = (firstEntry.vertice[0][0] + firstEntry.vertice[1][0] + firstEntry.vertice[2][0] + firstEntry.vertice[3][0]) / 4;
    firstEntryInImage[1] = (firstEntry.vertice[0][1] + firstEntry.vertice[1][1] + firstEntry.vertice[2][1] + firstEntry.vertice[3][1]) / 4;
    let furthestEntryInImage = Array(2);
    furthestEntryInImage[0] = (furthestEntry.vertice[0][0] + furthestEntry.vertice[1][0] + furthestEntry.vertice[2][0] + furthestEntry.vertice[3][0]) / 4;
    furthestEntryInImage[1] = (furthestEntry.vertice[0][1] + furthestEntry.vertice[1][1] + furthestEntry.vertice[2][1] + furthestEntry.vertice[3][1]) / 4;

    //get the center of the corresponding geometries in the model; in scene coordinate system
    let firstEntryInModel = cameraFrames.getKeyframeOrigin(firstEntry.id);
    let furthestEntryInModel = cameraFrames.getKeyframeOrigin(furthestEntry.id);

    //create new PlaneGeometry using the mapping result as the texture
    var texture = new THREE.TextureLoader().load(imgUrl);
    var geometry = new THREE.PlaneGeometry(MAPPING_INITIAL_SIZE, MAPPING_INITIAL_SIZE); //some initial size
    var material = new THREE.MeshBasicMaterial({map : texture, transparent: true});
    var mesh = new THREE.Mesh(geometry, material);
    //positioned in the center and rotated so that the front of the polygon shows up/ -y axis
    mesh.position.set(0,0,0);
    mesh.rotation.set(Math.PI / 2, 0, 0);

    //create vectors to the entries, in scene coordinate system
    let vectorFirstEntryInImage = new THREE.Vector3( (firstEntryInImage[0]/imgWidth * geometry.parameters.width) - (geometry.parameters.width/2),
        -1,
        -firstEntryInImage[1]/imgHeight * geometry.parameters.height + geometry.parameters.height - (geometry.parameters.height/2));
    let vectorFirstEntryInModel = new THREE.Vector3( firstEntryInModel[0],
        -1,
        firstEntryInModel[2]);

    let vectorFurthestEntryInImage = new THREE.Vector3( (furthestEntryInImage[0]/imgWidth * geometry.parameters.width) - (geometry.parameters.width/2),
        -1,
        -furthestEntryInImage[1]/imgHeight * geometry.parameters.height + geometry.parameters.height - (geometry.parameters.height/2));
    let vectorFurthestEntryInModel = new THREE.Vector3( furthestEntryInModel[0],
        -1,
        furthestEntryInModel[2]);
    let scalingFactor = new THREE.Vector3().copy(vectorFurthestEntryInModel).add(vectorFirstEntryInModel.negate()).length()/new THREE.Vector3().copy(vectorFurthestEntryInImage).add(vectorFirstEntryInImage.negate()).length();
    let translationVector = new THREE.Vector3().copy(vectorFurthestEntryInModel).add(vectorFurthestEntryInImage.multiplyScalar(scalingFactor).negate());

    mesh.scale.set(scalingFactor,scalingFactor,scalingFactor);
    mesh.position.x += translationVector.x;
    mesh.position.z += translationVector.z;
    mesh.position.y += lowest_pose;
    console.log(lowest_pose);

    scene.add(mesh);
}

let controlsInitiated = false;

function initiateControls() {
    // create a mouse action listener
    let mouseListener = function (btn, act, pos, vel) {
        if (btn == 0 && act != 0) {
            viewControls.addRot(vel[0], vel[1]);
        }
        else if (btn == 2 && act != 0) {
            viewControls.addMove(vel[0], vel[1])
        }
    };
    // create a mouse wheel action listener
    let wheelListener = function (rot) {
        viewControls.addZoom(rot);
    };
    mouseHandler = new MouseHandler(renderer.domElement, mouseListener);
    wheelHandler = new WheelHandler(renderer.domElement, wheelListener);
    controlsInitiated = true;
}

function loadLandmarks(landmarks) {
    var landmarkOutput = [];
    for (let landmark of landmarks) {
        let landmarkObj = {};
        landmarkObj["id"] = landmark.id;
        if (landmark.point_pos != undefined) {
            landmarkObj["point_pos"] = landmark.point_pos;
            landmarkObj["rgb"] = landmark.rgb;
        }
        landmarkOutput.push(landmarkObj)
    }
    for (let landmark of landmarkOutput) {
        pointCloud.updatePoint(landmark.id,
                               landmark.point_pos[0]*50,
                               landmark.point_pos[1]*50,
                               landmark.point_pos[2]*50,
                               landmark.rgb[0],
                               landmark.rgb[1],
                               landmark.rgb[2])
    }
}



// render method that updates each stats, camera frames, view controller, and renderer.
function render() {

    pointCloud.updatePointInScene(scene);

    cameraFrames.updateFramesInScene(scene);

    //if(chase_camera == false){
    // 仮　トラックボールコントロール用
    let delta = clock.getDelta();
    //trackballControls.update(delta);
    viewControls.update(delta);


    // render using requestAnimationFrame
    requestAnimationFrame(render);
    // render the Scene
    renderer.render(scene, camera);
}

// initialize gui by dat.gui
function initGui() {
    let gui = new dat.GUI({ width: 300 });

    gui.add(property, 'CameraMode', ['Above', 'Follow', 'Bird', 'Subjective']).onChange(setCameraMode);
    gui.add(property, 'FixAngle').onChange(toggleFixAngle);
    gui.add(property, 'LandmarkSize', 0, 4, 0.1).onChange(setPointSize);
    gui.add(property, 'KeyframeSize', 0, 4, 0.1).onChange(setKeyframeSize);
    gui.add(property, 'CurrentFrameSize', 0, 4, 0.1).onChange(setCurrentframeSize);
    gui.add(camera, 'far', 1000, 1000000, 1000).onChange(setFar);
    gui.add(property, 'DrawGraph').onChange(setGraphVis);
    gui.add(property, 'DrawGrid').onChange(setGridVis);
    gui.add(property, 'DrawPoints').onChange(setPointsVis);
    gui.add(property, 'LocalizationMode').onChange(setLocalizationMode);
    gui.add(property, 'ResetSignal').domElement.children[0].innerHTML = "<button onclick='onClickReset()'>reset</button>";
    gui.add(property, 'StopSignal').domElement.children[0].innerHTML = "<button onclick='onClickTerminate()'>terminate</button>";
}

function setCameraMode(val) {
    let suffix = "_rot";
    if (property.FixAngle) {
        suffix = "_fix";
    }
    cameraFrames.setCurrentFrameVisibility(val !== "Subjective");
    viewControls.setMode(val + suffix);
}
function toggleFixAngle(val) {
    // If view angle is fixed, camera could not be rotated.
    setCameraMode(property.CameraMode);
}
function setPointSize(val) {
    val = Math.pow(2, val);
    pointCloud.setPointSize(val);
}
function setKeyframeSize(val) {
    val = Math.pow(2, val);
    cameraFrames.setKeyframeSize(val);
}
function setCurrentframeSize(val) {
    val = Math.pow(2, val);
    cameraFrames.setCurrentFrameSize(val);
}
function setFar(val) {
    camera.updateProjectionMatrix();
}
function setGraphVis(val) {
    cameraFrames.setGraphVisibility(val);
}
function setGridVis(val) {
    grid.visible = val;
}
function setPointsVis(val) {
    pointCloud.setPointsVisibility(val);
}
function setLocalizationMode(val) {
    if (val == true) {
        socket.emit("signal", "disable_mapping_mode");
    }
    else {
        socket.emit("signal", "enable_mapping_mode");
    }
}
function onClickReset() {
    socket.emit("signal", "reset");
}
function onClickTerminate() {
    socket.emit("signal", "terminate");
}

// function that converts array that have size of 16 to matrix that shape of 4x4
function array2mat44(mat, array) {
    for (let i = 0; i < 4; i++) {
        let raw = [];
        for (let j = 0; j < 4; j++) {
            let k = i * 4 + j;
            let elm = array[k];
            raw.push(elm);
        }
        mat.push(raw);
    }
}
function loadProtobufData(obj, keyframes, edges, points, referencePointIds, currentFramePose) {
    for (let keyframeObj of obj.keyframes) {
        let keyframe = {};
        keyframe["id"] = keyframeObj.id;
        if (keyframeObj.pose != undefined) {
            keyframe["camera_pose"] = [];
            array2mat44(keyframe["camera_pose"], keyframeObj.pose.pose);
        }
        keyframes.push(keyframe);
    }
    for (let edgeObj of obj.edges) {
        edges.push([edgeObj.id0, edgeObj.id1])
    }
    for (let landmarkObj of obj.landmarks) {
        let landmark = {};
        landmark["id"] = landmarkObj.id;
        if (landmarkObj.coords.length != 0) {
            landmark["point_pos"] = landmarkObj.coords;
            landmark["rgb"] = landmarkObj.color;
        }
        points.push(landmark);
    }
    for (let id of obj.localLandmarks) {
        referencePointIds.push(id);
    }
    array2mat44(currentFramePose, obj.currentFrame.pose);

}

let mapSegment = undefined;
let mapMsg = undefined;
function initProtobuf() {
}

function receiveProtobuf(msg) {
    if (msg.length == 0 || mapSegment == undefined) {
        return;
    }

    let keyframes = [];
    let edges = [];
    let points = [];
    let referencePointIds = [];
    let currentFramePose = [];

    let buffer = base64ToUint8Array(msg);
    let obj = mapSegment.decode(buffer);
    console.log(obj.messages[0].tag + " ; " + obj.messages[0].txt);

    if (obj.messages[0].tag == "RESET_ALL") {
        removeAllElements();
    }
    else {
        loadProtobufData(obj, keyframes, edges, points, referencePointIds, currentFramePose);
        updateMapElements(keyframes, edges, points, referencePointIds, currentFramePose);
    }
}

function receiveMsg(msg) {
    let buffer = base64ToUint8Array(msg);
    let obj = mapSegment.decode(buffer);
    console.log(obj.messages[0].tag + " ; " + obj.messages[0].txt);

}

function base64ToUint8Array(base64) {
    let binaryString = window.atob(base64);
    let len = binaryString.length;
    let bytes = new Uint8Array(len);
    for (var i = 0; i < len; i++) {
        bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes;
}

function updateMapElements(keyframes, edges, points, referencePointIds, currentFramePose) {
    cameraFrames.updateCurrentFrame(currentFramePose);
    viewControls.setCurrentIntrinsic(currentFramePose);

    if (cameraFrames.numValidKeyframe == 0 && keyframes.length == 0) {
        return;
    }

    for (let point of points) {
        let id = point["id"];
        if (point["point_pos"] == undefined) {
            pointCloud.removePoint(id);
        }
        else {
            let x = point["point_pos"][0] * GLOBAL_SCALE;
            let y = point["point_pos"][1] * GLOBAL_SCALE;
            let z = point["point_pos"][2] * GLOBAL_SCALE;
            let r = point["rgb"][0];
            let g = point["rgb"][1];
            let b = point["rgb"][2];
            pointCloud.updatePoint(id, x, y, z, r, g, b);
        }
    }
    for (let keyframe of keyframes) {
        let id = keyframe["id"];
        if (keyframe["camera_pose"] == undefined) {
            cameraFrames.removeKeyframe(id);
        }
        else {
            cameraFrames.updateKeyframe(id, keyframe["camera_pose"]);
        }
    }
    cameraFrames.setEdges(edges);


    let currentMillis = new Date().getTime();
    if (receiveTimestamp != 0) {
        let dt = currentMillis - receiveTimestamp;
        if (dt < 2) dt = 2;
        let fps = 1000.0 / dt;
        // adaptive update rate
        //viewControls.updateSmoothness(fps);
        /*console.log(("         " + parseInt(msgSize / 1000)).substr(-6) + " KB"
            + ("     " + (fps).toFixed(1)).substr(-7) + " fps, "
            + ("         " + pointCloud.nValidPoint).substr(-6) + " pts, "
            + ("         " + cameraFrames.numValidKeyframe).substr(-6) + " kfs");*/
    }
    receiveTimestamp = currentMillis;

    pointCloud.colorizeReferencePoints(referencePointIds);

}

function removeAllElements() {
    for (let id in pointCloud.vertexIds) {
        if (id < 0 || id == undefined) {
            continue;
        }
        pointCloud.removePoint(id);
    }
    for (let id in cameraFrames.keyframeIndices) {
        if (id < 0 || id == undefined) {
            continue;
        }
        cameraFrames.removeKeyframe(id);
    }
    cameraFrames.setEdges([]);
}

// calculate inverse of se3 pose matrix
function inv(pose) {
    let res = new Array();
    for (let i = 0; i < 3; i++) {
        res.push([0, 0, 0, 0]);
    }
    // - R^T * t
    res[0][3] = - pose[0][0] * pose[0][3] - pose[1][0] * pose[1][3] - pose[2][0] * pose[2][3];
    res[1][3] = - pose[0][1] * pose[0][3] - pose[1][1] * pose[1][3] - pose[2][1] * pose[2][3];
    res[2][3] = - pose[0][2] * pose[0][3] - pose[1][2] * pose[1][3] - pose[2][2] * pose[2][3];
    res[0][0] = pose[0][0]; res[0][1] = pose[1][0]; res[0][2] = pose[2][0];
    res[1][0] = pose[0][1]; res[1][1] = pose[1][1]; res[1][2] = pose[2][1];
    res[2][0] = pose[0][2]; res[2][1] = pose[1][2]; res[2][2] = pose[2][2];

    return res;
}

// window resize function
// The function is called in index.ejs
function onResize() {
    camera.aspect = document.getElementsByClassName('vslam_model')[0].offsetWidth / document.getElementsByClassName('vslam_model')[0].offsetHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(document.getElementsByClassName('vslam_model')[0].offsetWidth, document.getElementsByClassName('vslam_model')[0].offsetHeight);
}

let thumbEnlarge = false; // if thumbnail is clicked, that is enlarged and this flag is set
const THUMB_SCALING = 3; // thumbnail scaling magnification
const THUMB_HEIGHT = 96; // normally thumbnail height (width is doubled height)
const CANVAS_SIZE = [1024, 500]; // thumbnail image resolution
function onThumbClick() {

    thumbEnlarge = !thumbEnlarge; // inverse flag
    if (!thumbEnlarge) {
        document.getElementById("thumb").style.transform = 'translate(0px, 0px) scale(1)';
    }
    else {
        let x = THUMB_HEIGHT * (THUMB_SCALING - 1);
        let y = THUMB_HEIGHT / 2 * (THUMB_SCALING - 1);
        document.getElementById("thumb").style.transform = 'translate(' + x + 'px, ' + y + 'px) scale(' + THUMB_SCALING + ')';
    }

}
