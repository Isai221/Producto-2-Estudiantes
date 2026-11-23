// estudianteRoutes.js
const express = require('express');
const router = express.Router();
const estudianteController = require('../controllers/estudianteController');
const { verificarToken, esAdmin } = require('../middlewares/auth');

// Rutas protegidas
router.get('/', verificarToken, esAdmin, estudianteController.obtenerEstudiantes); // Solo Admin
router.get('/perfil', verificarToken, estudianteController.miPerfil); // Cualquier usuario logueado
router.get('/promedios', verificarToken, estudianteController.verPromedios); // Cualquier usuario
router.get('/reprobados', verificarToken, esAdmin, estudianteController.verReprobados); // Solo Admin

module.exports = router;