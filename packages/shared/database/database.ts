import mongoose from 'mongoose';
const uri = process.env.MONGODB_URI!;


const DATABASE_NAME = 'nina_app';

export async function connectDatabase() {
    return await mongoose.connect(uri + '/' + DATABASE_NAME);
}