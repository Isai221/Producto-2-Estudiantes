const prisma = require('../prisma');

// Solo ADMIN puede ver todos los estudiantes
exports.obtenerEstudiantes = async (req, res) => {
    const estudiantes = await prisma.estudiante.findMany({
        select: { id: true, nombre: true, email: true, rol: true, creadoEn: true }
    });
    res.json(estudiantes);
};

// ESTUDIANTE puede ver su propio perfil
exports.miPerfil = async (req, res) => {
    const estudiante = await prisma.estudiante.findUnique({
        where: { id: req.usuario.id },
        select: { id: true, nombre: true, email: true, rol: true }
    });
    res.json(estudiante);
};

// Consultar vistas (Usando SQL puro a través de Prisma)
exports.verPromedios = async (req, res) => {
    const promedios = await prisma.$queryRaw`SELECT * FROM vista_promedio_estudiante;`;
    res.json(promedios);
};

exports.verReprobados = async (req, res) => {
    const reprobados = await prisma.$queryRaw`SELECT * FROM vista_reprobados;`;
    res.json(reprobados);
};