import mongoose from 'mongoose';
const uri = process.env.MONGODB_URI!;


const DATABASE_NAME = 'nina_app';

export async function getDatabase() {
    return await mongoose.connect(uri + '/' + DATABASE_NAME);
}

getDatabase().then(() => {
    console.log('Connected to database');
}).catch((error) => {
    console.error('Error connecting to database:', error);
});