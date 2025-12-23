// /**
//  * Camera Page Functionality
//  */

// class CameraPage {
//     constructor() {
//         this.currentCamera = 0;
//         this.init();
//     }

//     init() {
//         this.setupEventListeners();
//         this.updateCameraInfo();
//     }

//     setupEventListeners() {
//         const changeCameraBtn = document.getElementById('changeCameraBtn');
//         if (changeCameraBtn) {
//             changeCameraBtn.addEventListener('click', () => this.changeCamera());
//         }

//         const cameraIndex = document.getElementById('cameraIndex');
//         if (cameraIndex) {
//             cameraIndex.addEventListener('change', (e) => {
//                 this.currentCamera = e.target.value;
//                 this.updateCameraInfo();
//             });
//         }
//     }

//     async changeCamera() {
//         const cameraIndex = document.getElementById('cameraIndex').value;

//         try {
//             const response = await fetch('/api/cam_changed', {
//                 method: 'POST',
//                 headers: {
//                     'Content-Type': 'application/json'
//                 },
//                 body: JSON.stringify({ cam_number: parseInt(cameraIndex) })
//             });

//             if (response.ok) {
//                 const data = await response.json();
//                 this.currentCamera = cameraIndex;
//                 this.updateCameraInfo();
//                 dashboardBase.showAlert(data.message, 'success');
//             } else {
//                 dashboardBase.showAlert('Kamera değiştirilirken hata oluştu', 'error');
//             }
//         } catch (error) {
//             console.error('Error changing camera:', error);
//             dashboardBase.showAlert('Hata: Kamera değiştirilemiyor', 'error');
//         }
//     }

//     updateCameraInfo() {
//         const currentCameraEl = document.getElementById('currentCamera');
//         if (currentCameraEl) {
//             currentCameraEl.textContent = this.currentCamera;
//         }
//     }
// }

// // Initialize when DOM is ready
// let cameraPage;
// document.addEventListener('DOMContentLoaded', () => {
//     cameraPage = new CameraPage();
// });
