const prisma = require('../prisma');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');

exports.registro = async (req, res) => {
    try {
        const { nombre, email, password, rol } = req.body;
        
        // Encriptar contraseña
        const salt = await bcrypt.genSalt(10);
        const passwordHash = await bcrypt.hash(password, salt);

        const nuevoEstudiante = await prisma.estudiante.create({
            data: {
                nombre,
                email,
                passwordHash,
                rol: rol || 'ESTUDIANTE' // Por defecto estudiante
            }
        });

        res.status(201).json({ mensaje: 'Usuario registrado', id: nuevoEstudiante.id });
    } catch (error) {
        res.status(400).json({ error: 'El correo ya existe o datos inválidos', detalle: error.message });
    }
};

exports.login = async (req, res) => {
    try {
        const { email, password } = req.body;
        
        const usuario = await prisma.estudiante.findUnique({ where: { email } });
        if (!usuario) return res.status(404).json({ error: 'Usuario no encontrado' });

        const passwordValida = await bcrypt.compare(password, usuario.passwordHash);
        if (!passwordValida) return res.status(401).json({ error: 'Contraseña incorrecta' });

        // Generar JWT
        const token = jwt.sign(
            { id: usuario.id, rol: usuario.rol },
            process.env.JWT_SECRET,
            { expiresIn: '2h' }
        );

        res.json({ token, usuario: { id: usuario.id, nombre: usuario.nombre, rol: usuario.rol } });
    } catch (error) {
        res.status(500).json({ error: 'Error en el servidor', detalle: error.message });
    }
};