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

/**
 * loads keyframes from a json file, and adds them to the three js renderer
 * @param keyframes the json file to load the keyframes from
 */
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

/**
 * loads landmarks from a json file, and adds them to the three js renderer
 * @param landmarks the json file to load the landmarks from
 */
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

/**
 * loads the mapping result and places it as a ground texture in the three js scene
 * also needs loaded keyframes to get the pose data
 * @param imgUrl url to the mapping image result
 * @param imgHeight width of the mapping image
 * @param imgWidth height of the mapping image
 * @param imgVertices vertices display the corner coordinates of the keyframes in the mapping image
 * needed to calculate scaling and rotation
 */
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

function setCameraMode(val) {
    let suffix = "_rot";
    if (property.FixAngle) {
        suffix = "_fix";
    }
    cameraFrames.setCurrentFrameVisibility(val !== "Subjective");
    viewControls.setMode(val + suffix);
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
